#
# The main search hooks for the Search Flask application.
#
from flask import (
    Blueprint, redirect, render_template, request, url_for
)

from week1.opensearch import get_opensearch

bp = Blueprint('search', __name__, url_prefix='/search')


# Process the filters requested by the user and return a tuple that is appropriate for use in: the query, URLs displaying the filter and the display of the applied filters
# filters -- convert the URL GET structure into an OpenSearch filter query
# display_filters -- return an array of filters that are applied that is appropriate for display
# applied_filters -- return a String that is appropriate for inclusion in a URL as part of a query string.  This is basically the same as the input query string
def process_filters(filters_input):
    # Filters look like: &filter.name=regularPrice&regularPrice.key={{ agg.key }}&regularPrice.from={{ agg.from }}&regularPrice.to={{ agg.to }}
    filters = []
    display_filters = []  # Also create the text we will use to display the filters that are applied
    applied_filters = ""
    for filter in filters_input:
        type = request.args.get(filter + ".type")
        display_name = request.args.get(filter + ".displayName", filter)
        applied_filters += "&filter.name={}&{}.type={}&{}.displayName={}".format(filter, filter, type, filter,
                                                                                 display_name)
        if type == "range":
            from_val = request.args.get(filter + ".from", None)
            to_val = request.args.get(filter + ".to", None)
            print("from: {}, to: {}".format(from_val, to_val))
            # we need to turn the "to-from" syntax of aggregations to the "gte,lte" syntax of range filters.
            to_from = {}
            if from_val:
                to_from["gte"] = from_val
            else:
                from_val = "*"  # set it to * for display purposes, but don't use it in the query
            if to_val:
                to_from["lt"] = to_val
            else:
                to_val = "*"  # set it to * for display purposes, but don't use it in the query
            the_filter = {"range": {filter: to_from}}
            filters.append(the_filter)
            display_filters.append("{}: {} TO {}".format(display_name, from_val, to_val))
            applied_filters += "&{}.from={}&{}.to={}".format(filter, from_val, filter, to_val)
        elif type == "terms":
            field = request.args.get(filter + ".fieldName", filter)
            key = request.args.get(filter + ".key", None)
            the_filter = {"term": {field: key}}
            filters.append(the_filter)
            display_filters.append("{}: {}".format(display_name, key))
            applied_filters += "&{}.fieldName={}&{}.key={}".format(filter, field, filter, key)
    print("Filters: {}".format(filters))

    return filters, display_filters, applied_filters



# Our main query route.  Accepts POST (via the Search box) and GETs via the clicks on aggregations/facets
@bp.route('/query', methods=['GET', 'POST'])
def query():
    opensearch = get_opensearch() # Load up our OpenSearch client from the opensearch.py file.
    # Put in your code to query opensearch.  Set error as appropriate.
    error = None
    user_query = None
    query_obj = None
    display_filters = None
    applied_filters = ""
    filters = None
    sort = "_score"
    sortDir = "desc"
    fromElement = 0
    if request.method == 'POST':  # a query has been submitted
        user_query = request.form['query']
        if not user_query:
            user_query = "*"
        sort = request.form["sort"]
        if not sort:
            sort = "_score"
        sortDir = request.form["sortDir"]
        if not sortDir:
            sortDir = "desc"
        fromElement = request.form['fromElement']    
        if not fromElement:
            fromElement = 0
        elif int(fromElement) < 0:
            fromElement = 0
        else:
            fromElement = int(fromElement)
        query_obj = create_query(user_query, [], sort, sortDir, fromElement)
    elif request.method == 'GET':  # Handle the case where there is no query or just loading the page
        user_query = request.args.get("query", "*")
        filters_input = request.args.getlist("filter.name")
        sort = request.args.get("sort", sort)
        sortDir = request.args.get("sortDir", sortDir)
        fromElement = request.args.get("fromElement", fromElement)
        if filters_input:
            (filters, display_filters, applied_filters) = process_filters(filters_input)

        query_obj = create_query(user_query, filters, sort, sortDir)
    else:
        query_obj = create_query("*", [], sort, sortDir)

    print("query obj: {}".format(query_obj))

    #### Step 4.b.ii
    # DONE
    try:
        response = opensearch.search(body=query_obj, index='bbuy_products')   
    except Exception as e: # opensearchpy.exceptions.RequestError as ex:
        print("catch exception")
        print(e)
        error = True
    # Postprocess results here if you so desire

    if error is None:
        return render_template("search_results.jinja2", query=user_query, search_response=response,
                               display_filters=display_filters, applied_filters=applied_filters,
                               sort=sort, sortDir=sortDir, fromElement=fromElement)
    else:
        redirect(url_for("index"))


def create_query(user_query, filters, sort="_score", sortDir="desc", fromElement=0):
    print("Query: {} Filters: {} Sort: {}".format(user_query, filters, sort))
    ### Step 4.b.i is done here

    if user_query == '*':
        inner_query =  {"match_all": {}}
    else:
        inner_query = {
            "query_string": {
                "query" : user_query,
                "fields": ["name^100", "shortDescription^50", "longDescription^10", "department"],
                "phrase_slop": 3
            }
        }
          
    query_obj = {
        'size': 10,
        "from": fromElement * 10, # page * 10 elements 
        "query": {
            "bool": {
                "must": inner_query,
                "filter": filters
            }
        },
        "sort": [{sort: {"order": sortDir}}],
        "highlight": {
            "fields": {
                "name": { "type": "plain" },
                "shortDescription": { "type": "plain"},
                "longDescription": { "type": "plain"}
            }
        },
        "aggs": {
            #### Step 4.b.i: create the appropriate query and aggregations here
            "regularPrice": {
                "range":{
                    "field": "regularPrice",
                    "ranges": [
                        { "key": "$", "to": 99},
                        { "key": "$$", "from": 99, "to": 200},
                        { "key": "$$$", "from": 200, "to": 300  },
                        { "key": "$$$$", "from": 300, "to": 400 },
                        { "key": "$$$$$", "from": 400, "to": 500 },
                        { "key": "$$$$$$", "from": 500 }
                    ]
                }
            },
            "department": {
                "terms":{
                    "field": "department.keyword"
                }
            },
            "manufacturer": {
                "terms":{
                    "field": "manufacturer.keyword",
                    "size": 10,
                    "min_doc_count": 0,
                    "exclude": "UNKNOWN|Unknown"
                }
            },
            "missing_images": {
                "missing":{"field": "image.keyword"}
            }
        }
    }
    return query_obj
