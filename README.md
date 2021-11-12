# cg-get-pcm-data
Gets Prisma SDWAN PCM Data for all sites and Internet interfaces and compares with the configured bandwidth in a CSV file

```
CloudGenix Get-PCM Throughput Script
---------------------------------------
Writes the past 7-days bandwidth average dailies and the 7-day average for each SPOKE site.
Output is placed in a CSV file
optional arguments:
  -h, --help            show this help message and exit
  --token "MYTOKEN", -t "MYTOKEN"
                        specify an authtoken to use for CloudGenix authentication
  --authtokenfile "MYTOKENFILE.TXT", -f "MYTOKENFILE.TXT"
                        a file containing the authtoken
  --csvfile csvfile, -c csvfile
                        the CSV Filename to write the BW averages to
  --days days, -d days  The number of days to average (default=1)
  --threshold threshold, -s threshold
                        The average threshold in decimal (default=.80 for 80 percent)
```
