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

## Performance Optimization TODO
- Current architecture has two sequential phases that could run in parallel:
  1. Main logs (using exact file names via GetExactFilesFunction) - relatively fast
  2. Auxiliary logs (using file name filters via GetFilesFunction) - much slower than expected

- Detailed analysis of auxiliary log processing workflow:
  - The state machine executes "Process Other Logs" after "Process Main Log Types" (line 187 in combine_log_files.asl.yaml)
  - GetFilesFunction retrieves all objects with minimal prefix filtering, then filters by date patterns
  - DetermineOperationTypeFunction then checks every file size to determine operation type
  - Either CopyLogFilesFunction or CombineLogFilesFunction is invoked based on operation type
  - Each function operates on batches of files, with continuation markers for long-running operations

- Performance bottlenecks identified:
  1. Sequential processing where parallel execution is possible
     - Main and auxiliary logs processing could be executed in parallel
     - Process Other Logs (auxiliary) only starts after Process Main Log Types completes
     - These operations are independent and don't share resources that would cause contention
  
  2. Inefficient file filtering in auxiliary logs path
     - GetFilesFunction lists all objects in the bucket with minimal prefix filtering (line 24 in get_files/app.py)
     - Unlike GetExactFilesFunction which uses targeted prefixes, GetFilesFunction scans entire buckets
     - DetermineOperationTypeFunction makes separate HEAD requests for each file
     - all_files_large() makes sequential HEAD requests without batching/pagination:
       ```python
       def all_files_large(bucket_name, files):
           for file in files:
               # Get file size from S3
               response = s3_client.head_object(Bucket=bucket_name, Key=file)
               size = response['ContentLength']
               if size < MIN_SIZE:
                   return False
           return True
       ```
     - This is a major bottleneck as it makes a new HTTP request for each file
     - While it does terminate early when finding a small file, it must make sequential requests
     - Every HEAD request incurs network latency, adding up significantly with large file lists
  
  3. S3 connection handling inconsistencies
     - CombineLogFilesFunction properly uses connection pooling (max_pool_connections=50) with retries
     - Other functions (GetFilesFunction, GetExactFilesFunction) don't use connection pooling
     - No consistent retry strategy across all functions
     - Connection pooling is critical for functions making many S3 operations, as it:
       * Reduces TCP/TLS handshake overhead
       * Allows for HTTP connection reuse
       * Significantly improves throughput for Lambda functions making many S3 calls
  
  4. Multipart upload operations limitations
     - CombineLogFilesFunction uses S3 multipart uploads that require sequential processing by design
     - S3 multipart upload restrictions prevent batch combination of files (all parts except last must be ≥5MB)
     - The function is already well-optimized with connection pooling and continuation handling
     - The state machine calls this function in parallel via Map states for different log sets

- Algorithm differences between main and auxiliary logs:
  1. Main logs (fast path):
     - Uses GetExactFilesFunction that searches specific, known prefixes
     - Only looks in known date patterns and account IDs
     - No file size checking - combines all files regardless of size
  
  2. Auxiliary logs (slow path):
     - GetFilesFunction does a full bucket scan with minimal filtering
     - DetermineOperationTypeFunction checks all file sizes with sequential HEAD requests
     - Checks if files are already large enough (> MIN_SIZE) to skip combination

- Instrumentation options for performance analysis:
  1. CloudWatch logs with precise timestamps and metrics
     - Add timing code around critical sections in Lambda functions
     - Log metrics like file sizes, counts, and processing times
     - Example: Monitor time spent on:
       * S3 listing operations
       * File filtering
       * S3 HEAD operations
       * Multipart upload operations
  
  2. AWS X-Ray
     - Enable X-Ray tracing on Lambda functions and Step Functions
     - Add custom subsegments for precise timing of operations
     - Use X-Ray SDK annotations to add metadata to traces
     - Can visualize performance bottlenecks and service dependencies
  
  3. CloudWatch Lambda Insights
     - Enable Enhanced Monitoring for detailed performance metrics
     - Monitor memory usage, CPU usage, and network activity
     - Identify resource constraints affecting performance
  
  4. Custom metrics with CloudWatch
     - Use CloudWatch PutMetricData to publish custom metrics
     - Create dashboard for aggregate performance visualization
     - Set alarms for performance thresholds

- Optimization opportunities:
  1. State machine restructuring
     - Modify state machine to allow parallel processing of main and auxiliary logs
     - Use Map state with higher MaxConcurrency values where appropriate
  
  2. S3 operation optimization
     - Add consistent connection pooling to all Lambda functions
     - Use S3 batch operations for multiple file operations
     - Implement pagination for large object listings
     - Consider using S3 Inventory for faster file listing instead of ListObjectsV2
  
  3. Lambda function optimizations
     - Increase memory allocation where beneficial (benchmark to verify)
     - Optimize Python code (use generators, reduce memory usage)
     - Batch S3 operations where possible
     - Replace sequential HEAD requests with batch operations:
       * Use S3 batch operations or parallel processing to check file sizes
       * Sample a subset of files to determine operation type instead of checking all
       * Consider early termination once a small file is found
  
  4. Smart file filtering
     - Improve prefix filtering to reduce the initial result set
     - Use more selective patterns when filtering dates
     - Optimize file size checking with batched or sampled approaches

- Next steps:
  1. Implement instrumentation
  2. Analyze performance data to validate bottlenecks
  3. Restructure state machine to allow parallel processing of main and auxiliary logs
  4. Optimize high-latency operations in the auxiliary logs processing path