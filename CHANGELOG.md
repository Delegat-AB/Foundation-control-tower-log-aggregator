# Change Log

## v1.0.9
    * Continuation mechanism in place to avoid lambda timeouts for large log files
      or large amounts of log files.

## v1.0.8
    * Flow change: first the main logs, then the additional logs. Parallelism in the
      latter temporarily set to 1 and debug printouts added.

## v1.0.7
    * The filler file is now exactly 5MB in size and sparse.

## v1.0.6
    * Fixed the 1B bug when aggregation regions are specified.

## v1.0.5
    * Specified boto3 version 1.33.12.

## v1.0.4
    * Added final slash to prefix string now required to work as a prefix.

## v1.0.3
    * Corrected bug to select no buckets when the prefix list is empty.

## v1.0.2
    * Refreshed deployment scripts.

## v1.0.1
    * Open-source credits and URLs
    * Fixed installer initial stackset creation.

## v1.0.0
    * Initial release.
