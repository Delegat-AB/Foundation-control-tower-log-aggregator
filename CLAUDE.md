# Claude Operating Guidelines for Control Tower Log Aggregator

## Build & Deploy Commands
- Build project: `sam build --parallel`
- Deploy to default region: `./deploy`
- Deploy with dry run: `./deploy --dry-run`
- Process historical logs: Use ProcessHistoricalMainLogsSM Step Function with appropriate JSON input

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

## Performance Optimization TODO
- Current architecture has two sequential phases that could run in parallel:
  1. Main logs (using exact file names via GetExactFilesFunction) - relatively fast
  2. Auxiliary logs (using file name filters via GetFilesFunction) - much slower than expected

- Performance bottlenecks identified:
  1. Sequential processing where parallel execution is possible
     - Main and auxiliary logs processing could be executed in parallel
     - Process Other Logs (auxiliary) only starts after Process Main Log Types completes
  
  2. Inefficient file filtering in auxiliary logs path
     - GetFilesFunction lists all objects in the bucket with minimal prefix filtering
     - DetermineOperationTypeFunction makes separate HEAD requests for each file
     - all_files_large() makes sequential HEAD requests without batching/pagination
  
  3. S3 connection handling in some functions
     - CombineLogFilesFunction uses connection pooling (max_pool_connections=50)
     - Other functions (GetFilesFunction, GetExactFilesFunction) don't use connection pooling
     - No consistent retry strategy across functions
  
  4. Multipart upload operations in CombineLogFilesFunction
     - Complex aggregation logic with multiple S3 operations per file
     - Sequential processing of each file
     - No parallel aggregation of independent file sets

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
     - Replace sequential HEAD requests with batch operations
  
  4. Smart file filtering
     - Improve prefix filtering to reduce the initial result set
     - Use more selective patterns when filtering dates
     - Optimize file size checking with batched or sampled approaches

- Next steps:
  1. Implement instrumentation
  2. Analyze performance data to validate bottlenecks
  3. Restructure state machine to allow parallel processing of main and auxiliary logs
  4. Optimize high-latency operations in the auxiliary logs processing path