# openDS

Tools for open digital specimens openDS, see https://github.com/DiSSCo/openDS

## Galaxy workflow tool

[`add_collector_metadata`](./add_collector_metadata) — add meta data for collector names previously recognised by OCR. It searches Bionomia and WikiData

Get help
```bash
python 'main.py' -h
# usage: main.py [-h] -i INPUT -o OUTPUT -c COLLECTOR_LIST
# 
# Searching for collector meta data at Bionomia and WikiData by using their query service, and add these data to the 
# output, the open Digital Specimen object (openDS). It adds just the data and no decision is made belonging to the 
# real collector.
# 
# optional arguments:
#   -h, --help            show this help message and exit
#   -i INPUT, --input INPUT
#                         input file of a JSON openDS
#   -o OUTPUT, --output OUTPUT
#                         output file of a JSON openDS
#   -c COLLECTOR_LIST, --collector_list COLLECTOR_LIST
#                         One collector name, e.g. from optical recognition (OCR) analysis, OR a semicolon separated list 
#                         of multiple collector names: The 1st name is regarded as the very first collector, the 2nd as 
#                         second collector etc.. (maximum 10 findings per collector)
# 
# Several data are provided (in 'specimen_collector_search:results:…') but the data in common for both query services are: 
# fullname, lifespan, thumbnail, description, identifiers, score (score is decided by the service itself). It does 
# not handle organisations (yet), only human beings, alias persons.
```

Test case, search 1 collector “Meigen“:
```bash
python 'main.py' -i ./test-data/open-ds-input.json -o ./test-data/open-ds-output.json -c 'Meigen'
```

Test case, search 2 collectors (regarding the collector time line): Linné is the 1st collector, Groom is the 2nd collector in rank: 
```bash
python 'main.py' -i ./test-data/open-ds-input.json -o ./test-data/open-ds-output.json -c 'Linné; Groom'
```