# Claude Operating Guidelines for Control Tower Log Aggregator

## Build & Deploy Commands
- Build project: `sam build --parallel`
- Deploy to default region: `./deploy`
- Deploy with dry run: `./deploy --dry-run`
- Process historical logs: Use ProcessHistoricalMainLogsSM Step Function with appropriate JSON input (note: this is only run during initial setup, not daily)

## Testing
- Project is primarily infrastructure-as-code without traditional test patterns
- Testing is done through AWS deployment and monitoring CloudWatch logs

## Code Style Guidelines
- Python version: 3.12
- Imports: Standard library first, followed by boto3/AWS, then project modules
- Error handling: Use try/except blocks for AWS API calls with appropriate retries
- Logging: Use Python's logging module with INFO level for operational messages
- Function parameters: Use descriptive parameter names and docstrings
- Variable naming: Use snake_case for variables and functions, PascalCase for classes
- AWS resources: Follow Control Tower naming conventions for all resources
- S3 operations: Use connection pooling for high-throughput operations

## AWS Lambda Behavior
- Lambda functions are ephemeral and stateless - a new container may be initialized for each invocation
- Code outside the Lambda handler runs on cold starts (when a new container is initialized)
- Connection pooling benefits are within a single Lambda invocation, not between invocations
- Connection pooling is still valuable in Lambda functions that make multiple S3 API calls:
  - Eliminates connection establishment overhead (TCP handshakes, TLS negotiation)
  - Reuses HTTP connections instead of creating new ones for each S3 operation
  - Particularly important for functions making dozens or hundreds of S3 operations

## Performance Optimization Analysis

### Performance Issue Summary
- Main logs processing: ~7m 42s
- Auxiliary logs processing: ~1h 23m (83 minutes)
- Total execution time: ~1h 30m

### Detailed Timing Analysis
Analysis of stats.txt reveals the following timing breakdown for auxiliary logs processing:

1. **CombineLogFiles**: 
   - Most time-consuming operation (~65 minutes total)
   - Multiple executions run for exactly 13 minutes each
   - Properly uses continuation markers to handle Lambda timeout constraints
   - Already optimized with connection pooling and efficient multipart upload logic

2. **DeleteOriginals**: 
   - Second most expensive operation (~3 minutes total)
   - Final execution takes significantly longer (2:49.925) than earlier calls
   - Already using S3 batch operations (up to 1000 objects per request)
   - Escalating execution times as object count increases

3. **GetOtherLogFiles**: 
   - ~31.75 seconds total
   - One outlier execution takes 14.577s vs 1.8-3s for others
   - Full bucket scan with minimal filtering

4. **DetermineOperationType**:
   - ~11 seconds total
   - Sequential HEAD requests for file size checking
   - Early termination when finding small files

### Performance Bottlenecks Confirmed
1. **S3 connection handling inconsistencies**:
   - CombineLogFilesFunction properly uses connection pooling (max_pool_connections=50) with retries
   - Other functions lack connection pooling, including DeleteOriginals which handles large operations
   - No consistent retry strategy across all functions

2. **Inefficient file filtering in auxiliary logs path**:
   - GetFilesFunction does a full bucket scan with minimal filtering
   - Unable to use narrower prefix filtering due to unpredictable date patterns in file names
   - DetermineOperationTypeFunction makes sequential HEAD requests without connection pooling

3. **Sequential processing flow**:
   - Auxiliary logs processing starts only after main logs processing completes
   - CombineLogFiles runs in 13-minute intervals due to timeout handling (by design)
   - DeleteOriginals shows escalating execution times with increasing object counts

### Optimization Priorities
1. **Add connection pooling everywhere**:
   - Immediate priority: Add to all Lambda functions consistently
   - Use the same configuration across all functions: `max_pool_connections=50, retries={'max_attempts': 10}`
   - Critical for DeleteOriginals which shows significant performance degradation with scale

2. **Improve S3 object listing efficiency**:
   - Evaluate S3 Inventory for faster object listing instead of ListObjectsV2
   - S3 Inventory provides daily or weekly CSV/ORC/Parquet files listing all objects
   - Can be faster than ListObjectsV2 for complete bucket scans

3. **Optimize DeleteOriginals function**:
   - Improve version handling and pagination
   - Increase memory allocation for potentially better performance
   - Analyze if excessive version history is causing the escalating execution times

4. **Optimize DetermineOperationType**:
   - Add connection pooling for HEAD requests
   - Consider sampling approach instead of checking all files
   - Implement parallel HEAD requests for file size checking

5. **Later: Parallel main and auxiliary processing**:
   - Modify state machine to process main and auxiliary logs concurrently
   - Performance impact will be limited by the slower auxiliary processing
   - Should be considered after addressing core performance issues

### Next Steps
1. **Completed improvements**:
   - Added connection pooling to all Lambda functions using consistent configuration:
     ```python
     from botocore.config import Config
     
     s3_config = Config(
         max_pool_connections=50,
         retries={'max_attempts': 10}
     )
     
     s3_client = boto3.client('s3', config=s3_config)
     ```
   - All S3 operations now use connection pooling to reduce TCP/TLS overhead and allow HTTP connection reuse
   - Consistent retry policy implemented across all functions

2. **Pending immediate improvements**:
   - Increase memory allocation for DeleteOriginals function
   - Implement logging to identify exact bottlenecks

3. **Medium-term optimizations**:
   - Set up S3 Inventory for faster object listing
   - Optimize DeleteOriginals version handling
   - Implement sampling in DetermineOperationType

4. **Long-term restructuring**:
   - Modify state machine for parallel processing
   - Consider architecture changes to reduce dependency on full bucket scans

### Performance Impact Analysis
- Timing data collected before optimization: See stats.txt
- Timing data after connection pooling improvements: Pending (stats2.txt)
- Expected improvement mainly in DeleteOriginals function and functions processing large numbers of S3 operations