#!/usr/bin/env python

import logging

DEBUG_MODE = False  # internal debug apart from logging
if DEBUG_MODE:
    from pprint import  pprint
    import time
    starttime = time.time()

# from os import path
from utils import parse_args, write_opends_to_output_file, get_data, parse_json_resp


logging.config.fileConfig('logger.conf')

log = logging.getLogger('main')


@parse_args
def __main__(opends_json, output_file, collector_list):
    # __main__(opends_json, output_file, collector_list):
    # python 'main.py' -i ./test-data/open-ds-input.json -o ./test-data/open-ds-output.json --collector_list 'Linné'
    #
    # general example:
    # __main__(opends_json, output_file, taxon, image)
    # -> needs  options --image and --taxon
    # python 'main.py' -i ./test-data/open-ds-input.json -o ./test-data/open-ds-output.json --image 'file.jpeg' --taxon 'a taxon'



    log.debug("Running SDR Tool Search Collector IDs")

    ####### Tool to do it's thing and modify opends_json #######
    # opends_json conceptually:
    # "specimen_collector_search": {
    #     "results": {
    #         "wikidata": [
    #            [ {"1result1"}, {"1result2"} ],
    #            [ {"2result1"} ],
    #            [ {"3result1"}, {"3result2"}, {"3result3"} ]
    #         ],
    #         "bionomia": [
    #            [ {"1result1"}, {"1result2"}, {"1result3"}, {"1result4"} ],
    #            [ {"2result1"}, {"2result2"} ],
    #            [ {"3result1"} ]
    #         ]
    #     },
    #     "summary": [
    #       "service 1 all results’ summary 1result, 2result, 3result",
    #       "service 2 all results’ summary 1result, 2result, 3result"
    #     ]
    # }
    # add findings directly to openDS
    opends_json['specimen_collector_search'] = {
        'results': {'bionomia': [], 'wikidata': []},
        'summary': []  # always have a summary
    }

    # TODO may be let query services work in parallel (?package multiprocessing)

    ### get requests in parallel
    resp_data = get_data(collector_list=collector_list)
    parse_json_resp(resp_data, opends_json)

    # TODO: Should we validate the output of the tool against openDS schema

    # always print summary
    print(
        '\n'.join(str(s) for s in opends_json['specimen_collector_search']['summary'])
    )

    ####### Write the modified opends_json to the output_file #######
    write_opends_to_output_file(opends_json, output_file)

    print("Time consumed for the process:", time.time() - starttime) if DEBUG_MODE else ''

if __name__ == "__main__":
    __main__()
