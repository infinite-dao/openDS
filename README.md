# openDS

Tools for open digital specimens openDS, see https://github.com/DiSSCo/openDS

## Galaxy workflow tool

### Add Collector Metadata

[`add_collector_metadata`](./add_collector_metadata) — add meta data for collector names previously recognised by OCR. It searches Bionomia and WikiData and it just adds possible metadata without making a decision of the collector match. 

TODO
- discuss the properties and structure for openDS see people linkage [issue #29 (DiSSCo/openDS)](https://github.com/DiSSCo/openDS/issues/29) 
- set the galaxy xml integration right
- WikiData query is slow: optimise WikiData SPARQL query to get fast results (search 2 names takes 5 to 8 seconds)

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

Test case, search 2 collectors: Linné is the 1st collector, Groom is the 2nd collector in rank, regarding the collector history time line: 
```bash
python 'main.py' -i ./test-data/open-ds-input.json -o ./test-data/open-ds-output.json -c 'Linné; Groom'
```

#### openDS Structure

See also
- documentation and screenshots in [`add_collector_metadata/doc/`](./add_collector_metadata/doc/).
- discussion of people linkage in [issue #29 (DiSSCo/openDS)](https://github.com/DiSSCo/openDS/issues/29) 

Data with *full results* searching 3 collector names with 2 data services:
```json
{
    "specimen_collector_search": {
        "results": {
            "wikidata": [
                [ {"1result1"}, {"1result2"} ],
                [ {"2result1"} ],
                [ {"3result1"}, {"3result2"}, {"3result3"} ]
            ],
            "bionomia": [
                [ {"1result1"}, {"1result2"}, {"1result3"}, {"1result4"} ],
                [ {"2result1"}, {"2result2"} ],
                [ {"3result1"} ]
          ]
        },
        "summary": [
            "service 1 all results’ summary 1result, 2result, 3result",
            "service 2 all results’ summary 1result, 2result, 3result"
        ]
    }
}
```

Data with *no results* searching 3 collector names with 2 data services:
```json
{
    "specimen_collector_search": {
        "results": {
            "wikidata": [
              [],
              [],
              []
            ],
            "bionomia": [
              [],
              [],
              []
            ]
        },
        "summary": [
            "service 1 summary is always present also if results are available",
            "service 2 summary is always present also if results are available"
        ]
    }
}
```

Provided JSON properties in `results` in detail, that are *always present*:

- `fullname`
- `lifespan` (can be `null`)
- `thumbnail` (can be `null`)
- `description` (can be `null`)
- `identifiers`
- `score` (provided from the services)
- and all other property terms would be distinct to one of either query service