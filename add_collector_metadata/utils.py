#!/usr/bin/env python

import argparse
import json
import re
import sys
from functools import wraps

# bug fix import grequest https://stackoverflow.com/questions/56309763/grequests-monkey-patch-warning
from gevent import monkey as curious_george
curious_george.patch_all(thread=False, select=False)

import grequests # needs also request

import logging, logging.config

logging.config.fileConfig('logger.conf')

log = logging.getLogger('utils')

DEBUG_MODE = False  # internal debug apart from logging

if DEBUG_MODE:
    from pprint import pprint

wikidata_query_with_comments = """
SELECT ?item
   ?fullname
  (GROUP_CONCAT(DISTINCT ?givennameLabel; separator=" ") AS ?givennames)   
   ?familyname   
  (GROUP_CONCAT(DISTINCT ?personAltLabel; separator="; ") AS ?alternateNames)
  ?description
  ?thumbnail
  (GROUP_CONCAT(DISTINCT ?occupationLabel; separator="; ") AS ?occupations)
  # (GROUP_CONCAT(DISTINCT ?occupationLangLabel; separator="; ") AS ?occupationsWithLangPrefix)
  #?isBiologist
  # ?genderLabel
  (
    REPLACE(
      CONCAT(
        COALESCE(CONCAT("<",STR(?isni_id), ">"), ""), 
        COALESCE(CONCAT("<",STR(?viaf_id), ">"), ""), 
        CONCAT("<",str(?wikidata_id) , ">")     
      ), 
      "><", 
      "> | <" 
    )
    AS ?identifiers
  )
?lifespan
?score
?numApiOrdinal

#  ?wikidata_id ?viaf_id ?isni_id_search ?isni_id
WHERE {{
  SELECT DISTINCT * {{ # sub-select to order for GROUP_CONCAT
    SERVICE wikibase:mwapi {{
      bd:serviceParam wikibase:endpoint "www.wikidata.org";
                      wikibase:api "Search";
                      mwapi:srsearch "inlabel:{srsearch} haswbstatement:P31=Q5"; # (1) primary search …
                        # AND property instance_of=Human 
                        # could be optimized “inlabel:…” or without it
                      
                      # mwapi:srwhat "text";
                      mwapi:srlimit "10".
      ?itemId wikibase:apiOutput mwapi:title.
      ?numApiOrdinal wikibase:apiOrdinal true. # a kind of ordinal match or so
    }}
    BIND(IRI(CONCAT(STR(wd:), ?itemId)) AS ?item)
    BIND(MAX(?numApiOrdinal) as ?numApiOrdinal_max)
    BIND(ABS(?numApiOrdinal - ?numApiOrdinal_max) AS ?score) # inverse of numApiOrdinal as I understand the numApiOrdinal as rank, I guess
    OPTIONAL {{ # (2) occupation or subclass_of biologist (OPTIONAL is fast, non-OPTIONAL is slowing down query)
      {{ 
        ?item wdt:P106/wdt:P279* wd:Q864503 . # occupation (P106) / subclassOf (P279) ~ biologist (Q864503)
        # wd:Q864503 ^wdt:P279*/^wdt:P106 ?item . # inverse path
        hint:Prior hint:gearing "forward".
        BIND (True AS ?isBiologist) .
      }}
      UNION
      {{ 
        ?item wdt:P106/wdt:P279* wd:Q420 . # occupation (P106) / subclassOf (P279) ~ biology (Q420)
        # wd:Q420 ^wdt:P279*/^wdt:P106 ?item .
        hint:Prior hint:gearing "forward".
        BIND (True AS ?isBiologist) .
      }}       
      ?item rdfs:label ?personLabel FILTER (LANG(?personLabel) IN (
            "en"#, "fr" , "de"
          )
      ).
      ?item skos:altLabel ?personAltLabel FILTER ( LANG(?personAltLabel) IN (
            "en"#, "fr" , "de"
          )
      ).
      ?item schema:description ?personDescription_internal FILTER ( LANG(?personDescription_internal) IN (
            "en"#, "fr" , "de"
          )
      ).
    }}
    OPTIONAL {{
      ?item wdt:P735 ?givennameObj .
      ?givennameObj rdfs:label ?givennameLabel FILTER (
        LANG(?givennameLabel) IN (
          "en"#, "fr" , "de"
        )
      ).
    }}              
    OPTIONAL {{ 
      ?item wdt:P734 ?familynameObj .
      ?familynameObj rdfs:label ?familyname FILTER (
        LANG(?familyname) IN (
          "en"#, "fr" , "de"
        )
      ).
    }}
    OPTIONAL {{ 
      ?item wdt:P18 ?thumbnailObj 
      BIND(REPLACE(wikibase:decodeUri(STR(?thumbnailObj)), "http://commons.wikimedia.org/wiki/Special:FilePath/", "") as ?fileName) .
      BIND(REPLACE(?fileName, " ", "_") as ?safeFileName)
      BIND(MD5(?safeFileName) as ?fileNameMD5) .
      BIND(CONCAT(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/", 
        SUBSTR(?fileNameMD5, 1, 1), "/", 
        SUBSTR(?fileNameMD5, 1, 2), "/", 
        ?safeFileName, "/200px-", 
        REPLACE(?safeFileName, "^(.+[Ss][Vv][Gg])$", "$1.png")
      ) as ?thumbnail)
    }}    
    OPTIONAL {{
      ?item wdt:P106 ?occupation. BIND (True AS ?hasOccupation) .
      ?occupation rdfs:label ?occupationLabel # nesseccary for GROUP_CONCAT()
      ### en:botanist en:zoologist etc. with language prefix
      BIND (LANG(?occupationLabel) AS ?occupationLang)
      BIND (CONCAT(?occupationLang, ":", ?occupationLabel) AS ?occupationLangLabel)
      FILTER (LANG(?occupationLabel) IN (
        "en" #, "fr" , "de"
        )
      ) .
    }}
    # OPTIONAL {{ 
    ?item wdt:P569 ?dateOfBirth .
    OPTIONAL {{
      ?item p:P569/psv:P569 [ 
        wikibase:timePrecision ?dateOfBirth_timePrecision;
      ]
    }}
    BIND (True AS ?hasBirthDate) .     
    # BIND(STR(?dateOfBirth) AS ?dateOfBirth_dateTimeValue).
    BIND(STRBEFORE(STR(?dateOfBirth),"T") AS ?dateOfBirth_dateValue).
    BIND(
      IF(?dateOfBirth_timePrecision < 11, # 11: day-month-year
        "00", SUBSTR(?dateOfBirth_dateValue, STRLEN(?dateOfBirth_dateValue) - 1,2)
      ) AS ?dateOfBirth_day
    )
    BIND(
      IF(?dateOfBirth_timePrecision < 10, # 10: ??-month-year
        "00", SUBSTR(?dateOfBirth_dateValue, STRLEN(?dateOfBirth_dateValue) - 4,2)
      ) AS ?dateOfBirth_month
    )
    BIND(
      CONCAT(
        "&#42; ",
        # DAY
        IF(
          ?dateOfBirth_timePrecision < 11, 
          "??", STR(DAY(?dateOfBirth))
        ),
        " ",
        # MONTH
        REPLACE(
            REPLACE(
              REPLACE(
                REPLACE(
                  REPLACE(
                    REPLACE(
                      REPLACE(
                        REPLACE(
                          REPLACE(
                            REPLACE(
                              REPLACE(
                                REPLACE(
                                  REPLACE(
                                    ?dateOfBirth_month,
                                    "12", "December"
                                  ), 
                                  "11", "November"
                                ), 
                                "10", "October"
                              ), 
                              "09", "September"
                            ), 
                            "08", "August"
                          ),           
                          "07", "July"
                        ),           
                        "06", "June"
                      ),           
                      "05", "May"
                    ),           
                    "04", "April"
                  ),           
                  "03", "March"
                ),           
                "02", "February"
              ),           
              "01", "January"
            ),
            "00", "month unknown"
          ),
        " ",
        STR(YEAR(?dateOfBirth))
      )
      AS ?dateOfBirth_formatted
    )
    # # # # # # # # # # # # # # # # # # # # 
    # death
    OPTIONAL {{ 
      ?item wdt:P570 ?dateOfDeath . 
      BIND (True AS ?hasDeathDate) .      
      ?item p:P570/psv:P570 [ 
        wikibase:timePrecision ?dateOfDeath_timePrecision_internal;
      ]
      BIND(STRBEFORE(STR(?dateOfDeath),"T") AS ?dateOfDeath_dateValue).
    }}
    # set ?dateOfDeath_timePrecision or use NA (not available)
    BIND(IF(BOUND(?dateOfDeath_timePrecision_internal), ?dateOfDeath_timePrecision_internal, -1) AS ?dateOfDeath_timePrecision)
    BIND(
      IF(?dateOfDeath_timePrecision < 11, # 11: day-month-year
        "00", SUBSTR(?dateOfDeath_dateValue, STRLEN(?dateOfDeath_dateValue) - 1,2)
      ) AS ?dateOfDeath_day
    )
    BIND(
      IF(?dateOfDeath_timePrecision < 10, # 10: ??-month-year
        "00", SUBSTR(?dateOfDeath_dateValue, STRLEN(?dateOfDeath_dateValue) - 4,2)
      ) AS ?dateOfDeath_month
    )
    BIND(
      IF(
        ?dateOfDeath_timePrecision = -1, 
        IF(YEAR(NOW()) - YEAR(?dateOfBirth) > 80,"?? &dagger;", "n.a."),
        CONCAT(
          # DAY
          IF(
            ?dateOfDeath_timePrecision < 11, 
            "??", STR(DAY(?dateOfDeath))
          ),
          " ",
          # MONTH
          REPLACE(
            REPLACE(
              REPLACE(
                REPLACE(
                  REPLACE(
                    REPLACE(
                      REPLACE(
                        REPLACE(
                          REPLACE(
                            REPLACE(
                              REPLACE(
                                REPLACE(
                                  REPLACE(
                                    ?dateOfDeath_month,
                                    "12", "December"
                                  ), 
                                  "11", "November"
                                ), 
                                "10", "October"
                              ), 
                              "09", "September"
                            ), 
                            "08", "August"
                          ),           
                          "07", "July"
                        ),           
                        "06", "June"
                      ),           
                      "05", "May"
                    ),           
                    "04", "April"
                  ),           
                  "03", "March"
                ),           
                "02", "February"
              ),           
              "01", "January"
            ),
            "00", "month unknown"
          ),
          " ",
          STR(YEAR(?dateOfDeath))
          , " &dagger;"
        ) # CONCAT
      )# If
      AS ?dateOfDeath_formatted
    )
    
    BIND(
      CONCAT(
        ?dateOfBirth_formatted, " &ndash; ", COALESCE(?dateOfDeath_formatted, "")
      ) AS ?lifespan
    ) .
    
    OPTIONAL {{ 
      ?item wdt:P21 ?genderObj. 
      ?genderObj rdfs:label ?genderLabel FILTER (
        LANG(?genderLabel) IN (
          "en"#, "fr" , "de"
        )
      ).
    }}
    BIND(
      CONCAT(
        COALESCE(CONCAT(?genderLabel, ': '), ""),
        COALESCE(?personDescription_internal, " no description yet")
      ) AS ?description
    )
    BIND(?personLabel as ?fullname)
    OPTIONAL {{ ?item wdtn:P214 ?viaf_id. }}
    OPTIONAL {{ 
      ?item  wdt:P213 ?ISNI_ID_internal . # the normalized wdtn:P213 does not work, so use formatter URL
      # wd:P213 wdt:P1630 ?ISNI_formatterurl.
    }}
    
    BIND(IRI(concat("https://isni.org/isni/", STR(REPLACE(?ISNI_ID_internal, " ", "")))) AS ?isni_id).
    # BIND(IRI(REPLACE(?ISNI_ID_internal, '^(.+)$', ?ISNI_formatterurl)) AS ?isni_id_search).
    BIND(URI(CONCAT("http://www.wikidata.org/entity/", ?itemId)) AS ?wikidata_id ) # perhaps redundant
    
    FILTER (
      # ?hasBirthDate = True # must be always present
      ?isBiologist = True && ?hasOccupation = True
    )
  }} ORDER BY ?occupationLabel  ?personAltLabel # ?occupationLang #
}}
GROUP BY 
  ?item 
  ?wikidata_id 
  ?viaf_id 
  # ?isni_id_search
  ?isni_id
  ?fullname 
    # ?givennameLabel
    ?familyname
  ?lifespan
  ?description
  ?thumbnail
  ?hasOccupation 
  # ?isBiologist
  ?genderLabel
  ?numApiOrdinal
  ?score
ORDER BY asc(?numApiOrdinal) ?personLabel ?occupation 
LIMIT 10
"""


def get_data(collector_list):
    """
    Get data from a list of collectors

    :param collector_list: list of names, optionally separate multiple names by semicolon
    :return: Request
    """

    default_header = {'Accept': 'application/sparql-results+json'}
    req = []
    for i, collector in enumerate(re.split(" *; *", collector_list)):
        collector_clean = collector.strip()
        if collector_clean:
            # https://api.bionomia.net/user.json?limit=10&q=Carl+Linné
            req_bionomia = grequests.get(
                'https://api.bionomia.net/user.json',
                headers=default_header,
                data={
                    "limit": 10,
                    "q": collector_clean
                },
                hooks={'response': [hook_factory(collector=collector_clean)]}
            )
            req.append(req_bionomia)

            req_wikidata = grequests.post(
                'https://query.wikidata.org/sparql',
                headers=default_header |
                        {"User-Agent": "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])},
                data={'query': wikidata_query_with_comments.format(srsearch=collector_clean)},
                hooks={'response': [hook_factory(collector=collector_clean)]}
            )
            req.append(req_wikidata)

    resp = grequests.map(req)  # send requests
    return resp


def hook_factory(*factory_args, **factory_kwargs):
    """
    Helper factory to modify grequest responses, e.g. via factory_kwargs (myspecial_keyword='some value')

    :param factory_args:
    :param factory_kwargs:
    :return: response_hook
    """
    def response_hook(response, *request_args, **request_kwargs):
        """
        Modify default response object and add `response.collector_search` (use factory_kwargs or factory_args)

        :param response: Response passed through
        :param request_args: Any argument based data
        :param request_kwargs: Any keyword based data
        :return: Response
        """
        #  add alwalys response.collector_search to response to know, what was searched for initially
        if 'collector' in factory_kwargs:
            response.collector_search = factory_kwargs['collector']  # add data
        else:
            response.collector_search = None
        return response  # the modified response
    return response_hook


def parse_json_resp(resp, opends_json):
    # print(resp)
    result_summary = {
        'service': {
            'Bionomia': [],
            'WikiData': []
        },
        'search': {
            'Bionomia': [],
            'WikiData': []
        }
    }
    # TODO check nesting
    for r in resp:
        data = json.loads(r.text)
        thisUrl = r.url
        if thisUrl == "https://query.wikidata.org/sparql":
            thisService = "WikiData"
            thisServiceCode = thisService.lower()
            result_summary['service'][thisService].append([])
            opends_json['specimen_collector_search']['results'][thisServiceCode].append([])
            iThisService = len(opends_json['specimen_collector_search']['results'][thisServiceCode]) - 1

            log.debug("try unpack {service} response".format(service=thisService))
            try:
                # if no results WikiData gives =>  "results": { "bindings": [ ] }
                if len(data["results"]["bindings"]):
                    for data_item in data["results"]["bindings"]:
                        if DEBUG_MODE:
                            print("## Service {service} data_item:".format(service=thisService))
                            pprint(data_item)

                        log.debug("found in {service}: {c}".format(
                            c=data_item["fullname"]["value"],
                            service=thisService
                        )
                        )
                        opends_json['specimen_collector_search']['results'][thisServiceCode][iThisService] \
                            .append({
                            "id": data_item["item"]["value"],
                            "fullname": data_item["fullname"]["value"],
                            "givennames": data_item["givennames"]["value"] if "givennames" in data_item else None,
                            "familyname": data_item["familyname"]["value"] if "familyname" in data_item else None,
                            "alternateNames": data_item["alternateNames"]["value"] if "alternateNames" in data_item else None,
                            "lifespan": data_item["lifespan"]["value"] if "lifespan" in data_item else None,
                            "thumbnail": data_item["thumbnail"]["value"] if "thumbnail" in data_item else None,
                            "description": data_item["description"]["value"] if "description" in data_item else None,
                            "occupations": data_item["occupations"]["value"] if "occupations" in data_item else None,
                            "numApiOrdinal": data_item["numApiOrdinal"]["value"],
                            "score": data_item["score"]["value"],
                            "identifiers": data_item["identifiers"]["value"]
                        })
                        result_summary['service'][thisService][iThisService].append(data_item["fullname"]["value"])
                        log.debug('appended results to {service}'.format(service=thisService))
                else:
                    result_summary['service'][thisService][iThisService].append('')
                    log.debug('appended results to {service} (nothing found)'.format(service=thisService))

                result_summary['search'][thisService].append(r.collector_search)

            except (KeyError, TypeError):
                pass
        elif thisUrl == "https://api.bionomia.net/user.json":
            thisService = "Bionomia"
            thisServiceCode = thisService.lower()
            result_summary['service'][thisService].append([])
            opends_json['specimen_collector_search']['results'][thisServiceCode].append([])
            iThisService = len(opends_json['specimen_collector_search']['results'][thisServiceCode]) - 1

            log.debug("try unpack {service} response".format(service=thisService))
            try:
                if len(data):
                    for data_item in data:

                        log.debug("found in Bionomia: {c}". format(c=data_item["fullname"]))

                        this_identifiers = []
                        if data_item['wikidata'] is not None:
                            this_identifiers.append(
                                '<http://www.wikidata.org/entity/{id}>'.format(id=data_item['wikidata'])
                            )
                        if data_item['orcid'] is not None:
                            this_identifiers.append(
                                '<https://orcid.org/{id}>'.format(id=data_item['orcid'])
                            )

                        data_item.update({'identifiers': " | ".join(this_identifiers)})

                        opends_json['specimen_collector_search']['results'][thisServiceCode][iThisService] \
                            .append(data_item)

                        log.debug('appended opends_json results to {service}'.format(service=thisService))
                        result_summary['service'][thisService][iThisService].append(str(data_item["fullname"]))
                else:
                    # result_summary['service'][thisService][iThisService] \
                    #     .append('n.a. for “{c}”'.format(c=r.collector_search))
                    result_summary['service'][thisService][iThisService].append('')
                    log.debug('appended opends_json results to {service} (nothing found)'.format(service=thisService))

                result_summary['search'][thisService].append(r.collector_search)

            except (KeyError, TypeError):
                pass
                # print(data)
    if DEBUG_MODE:
        print('## result_summary:')
        pprint(result_summary, depth=4)

    thisSummary = ""
    for iService, serviceTitle in enumerate(['Bionomia', 'WikiData']):
        # print("debug Service result:", serviceTitle)
        thisSummary = "Result set {i_service} by {service} Search:".format(
            i_service=iService + 1,
            service=serviceTitle
        )
        # TODO nesting
        for iSearchedName, searchName in enumerate(result_summary['search'][serviceTitle]):
            nResultsThisServiceSearch = len(result_summary['service'][serviceTitle][iSearchedName])
            name_results = result_summary['service'][serviceTitle][iSearchedName]
            if ''.join(name_results): # can have empty values
                thisSummary += \
                    " Found {result_text} for “{searching}”: {items}.".format(
                        result_text="one name" if nResultsThisServiceSearch == 1 else "{} names".format(nResultsThisServiceSearch),
                        searching=searchName,
                        items="; ".join(name_results)
                    )
            else:
                thisSummary += \
                    " Found {result_text} for “{searching}” as specimen collector.".format(
                        result_text="no name",
                        searching=searchName
                    )
        # summary for each collector: append text to mandatory summary
        if not ((0 <= iService) and (iService < len(opends_json['specimen_collector_search']['summary']))):
            opends_json['specimen_collector_search']['summary'].append([])

        if len(opends_json['specimen_collector_search']['summary'][iService]) > 0:
            opends_json['specimen_collector_search']['summary'][iService] += ' ' + thisSummary
        else:
            opends_json['specimen_collector_search']['summary'][iService] = thisSummary


# def get_sparql_results(endpoint_url, query):
#     """
#     Get results of query of SPARQL Protocol and RDF Query Language
#
#     :param endpoint_url:
#     :param query: SPARQL query string in SPARQL Protocol and RDF Query Language
#     :return: JSON
#     """
#     # TODO adjust user agent; see https://w.wiki/CX6
#     user_agent = "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])
#     sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
#     sparql.setMethod('POST')  # use "POST" if SPARQL query gets too large
#     sparql.setQuery(query)
#     sparql.setReturnFormat(JSON)
#
#     log.info("Get WikiData results from SPARQL query service …")
#     log.debug("get_sparql_results (for WikiData): setMethod POST, setReturnFormat JSON … and proceed to send and return data")
#
#     return sparql.query().convert()


# def get_bionomia_results(query):
#     """
#     Get results from api.bionomia.net like https://api.bionomia.net/user.json?limit=10&q=Carl+Linné
#
#     :param query: string to search for
#     :return: JSON
#     """
#     log.info("Get Bionomia results from API …")
#     log.debug("get_bionomia_results: before sending data to https://api.bionomia.net/user.json …")
#     resp = requests.get(
#         "https://api.bionomia.net/user.json",
#         params={
#             "limit": 10,
#             "q": query
#         }
#     )
#     log.debug("get_bionomia_results: after sending data")
#     data = json.loads(resp.text)
#     log.debug("get_bionomia_results: data as JSON converted")
#     return data


def parse_args(func):
    """
    Parse command line arguments and load openDS JSON file
    """
    @wraps(func)
    def decorated():
        parser = argparse.ArgumentParser(
            description="Searching for collector meta data at Bionomia and WikiData by using their query service,"
                        " and add these data to the output, the open Digital Specimen object (openDS)."
                        " It adds just the data and no decision is made belonging to the real collector.",
            epilog="Several data are provided (in 'specimen_collector_search:results:…')"
                   " but the data in common for both query services are:"
                   " fullname, lifespan, thumbnail, description, identifiers, score"
                   " (score is decided by the service itself)."
                   " It does not handle organisations (yet), only human beings, alias persons."
        )
        
        parser.add_argument(
            '-i',
            '--input',
            required=True,
            help='input file of a JSON openDS')

        parser.add_argument(
            '-o',
            '--output',
            required=True,
            help='output file of a JSON openDS')

        parser.add_argument(
             '-c',
             '--collector_list',
             required=True,
             type=str,
             help='One collector name, e.g. from optical recognition (OCR) analysis,'
                  ' OR a semicolon separated list of multiple collector names:'
                  ' The 1st name is regarded as the very first collector,'
                  ' the 2nd as second collector etc.. (maximum 10 findings per collector)'
        )

        args, unknown_args = parser.parse_known_args()
        
        # Unpack the unknown_args into the params dictionary
        params = {unknown_args[i].replace('--', ''): unknown_args[i+1] for i in range(0, len(unknown_args), 2)}
        
        with open(args.input) as json_file:    
            opends_json = json.load(json_file)

        return func(opends_json, args.output, args.collector_list, **params)
    
    return decorated


def write_opends_to_output_file(opends_json, output_file):
    """
    Write the modified opends_json to the output_file
    :param opends_json: JSON
    :param output_file: output  file
    :return:
    """

    with open(output_file, 'w') as f:
        json.dump(opends_json, f, indent=4 if DEBUG_MODE else None)
