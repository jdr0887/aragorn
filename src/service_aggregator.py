"""Literature co-occurrence support."""
import logging
import requests
import json
import os
import uuid

logger = logging.getLogger(__name__)


def entry(message, coalesce_type='none') -> dict:
    """
    Performs a operation that calls numerous services including strider, aragorn-ranker and answer coalesce

    :param message: should be of form Message
    :param coalesce_type: what kind of answer coalesce type should be performed
    :return: the result of the request
    """

    # make the call to traverse the various services to get the data
    final_answer: dict = strider_and_friends(message, coalesce_type)

    # return the answer
    return final_answer


def post(name, url, message, params=None):
    """
    launches a post request, returns the response.

    :param name: name of service
    :param url: the url of the service
    :param message: the message to post to the service
    :param params: the parameters passed to the service
    :return: dict, the result
    """
    if params is None:
        response = requests.post(url, json=message)
    else:
        response = requests.post(url, json=message, params=params)

    if not response.status_code == 200:
        logger.error(f'Error response from {name}, status code: {response.status_code}')
        return {}

    return response.json()


def strider(message) -> dict:
    """
    Calls strider
    :param message:
    :return:
    """
    url = 'http://robokop.renci.org:5781/query'

    # TODO: strider_answer = post(strider, url, message)

    # get the path to the test file
    test_filename = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'strider_out.json')

    # open the file and load it
    with open(test_filename, 'r') as tf:
        strider_answer = json.load(tf)

    num_answers = len(strider_answer['message']['results'])

    if (num_answers == 0) or ((num_answers == 1) and (len(strider_answer['results'][0]['node_bindings']) == 0)):
        logger.error(f'Error response from Strider, no answer returned.')
        return {}

    return strider_answer


def strider_and_friends(message, coalesce_type) -> dict:

    # create a guid
    uid: str = str(uuid.uuid4())

    # call strider service
    strider_answer: dict = strider(message)

    logger.debug(f"aragorn post ({uid}): {json.dumps({'message': message})}")

    # did we get a good response
    if len(strider_answer) == 0:
        logger.error("Error detected getting answer from Strider, aborting.")
        return {'error': 'Error detected getting answer from Strider, aborting.'}
    else:
        logger.debug(f'strider answer ({uid}): {json.dumps(strider_answer)}')

    # are we doing answer coalesce
    if coalesce_type != 'none':
        # get the request coalesced answer
        coalesce_answer: dict = post('coalesce', f'https://answercoalesce.renci.org/coalesce/{coalesce_type}', strider_answer)

        # did we get a good response
        if len(coalesce_answer) == 0:
            logger.error("Error detected getting answer from Answer coalesce, aborting.")
            return {'error': 'Error detected getting answer from Answer coalesce, aborting.'}
        else:
            logger.debug(f'coalesce answer ({uid}): {json.dumps(coalesce_answer)}')
    else:
        # just use the strider result in Message format
        coalesce_answer: dict = strider_answer

    # call the omnicorp overlay service
    omni_answer: dict = post('omnicorp', 'https://aragorn-ranker.renci.org/omnicorp_overlay', coalesce_answer)

    # get the path of where this file is. everything is relative to that
    this_path: str = os.path.dirname(os.path.realpath(__file__))

    # open the input and output files
    with open(os.path.join(this_path, 'omni_answer.json'), 'w') as out_file:
        # output the upgraded data into the output file
        json.dump(omni_answer, out_file, indent=2)

    # did we get a good response
    if len(omni_answer) == 0:
        logger.error("Error detected getting answer from aragorn-ranker/omnicorp_overlay, aborting.")
        return {'error': 'Error detected getting answer from aragorn-ranker/omnicorp_overlay, aborting'}
    else:
        logger.debug(f'omni answer ({uid}): {json.dumps(omni_answer)}')

    # call the weight correction service
    weighted_answer: dict = post('weight', 'https://aragorn-ranker.renci.org/weight_correctness', omni_answer)

    # open the input and output files
    with open(os.path.join(this_path, 'weighted_answer.json'), 'w') as out_file:
        # output the upgraded data into the output file
        json.dump(weighted_answer, out_file, indent=2)

    # did we get a good response
    if len(weighted_answer) == 0:
        logger.error("Error detected getting answer from aragorn-ranker/weight_correctness, aborting.")
        return {'error': 'Error detected getting answer from aragorn-ranker/weight_correctness, aborting.'}
    else:
        logger.debug(f'weighted answer ({uid}): {json.dumps(weighted_answer)}')

    # call the scoring service
    scored_answer: dict = post('score', 'https://aragorn-ranker.renci.org/score', {message: weighted_answer})

    # open the input and output files
    with open(os.path.join(this_path, 'scored_answer.json'), 'w') as out_file:
        # output the upgraded data into the output file
        json.dump(scored_answer, out_file, indent=2)

    # did we get a good response
    if len(scored_answer) == 0:
        logger.error("Error detected getting answer from aragorn-ranker/score, aborting.")
        return {'error': 'Error detected getting answer from aragorn-ranker/score, aborting.'}
    else:
        logger.debug(f'scored answer ({uid}): {json.dumps(scored_answer)}')

    # return the requested data
    return scored_answer


def one_hop_message(curie_a, type_a, type_b, edge_type, reverse=False) -> dict:
    """
    Creates a test message.
    :param curie_a:
    :param type_a:
    :param type_b:
    :param edge_type:
    :param reverse:
    :return:
    """
    query_graph = {
                    "nodes": [
                        {
                            "id": "a",
                            "type": type_a,
                            "curie": curie_a
                        },
                        {
                            "id": "b",
                            "type": type_b
                        }
                    ],
                    "edges": [
                        {
                            "id": "ab",
                            "source_id": "a",
                            "target_id": "b"
                        }
                    ]
                }

    if edge_type is not None:
        query_graph['edges'][0]['type'] = edge_type

        if reverse:
            query_graph['edges'][0]['source_id'] = 'b'
            query_graph['edges'][0]['target_id'] = 'a'

    message = {
                "message":
                {
                    "query_graph": query_graph,
                    'knowledge_graph': {"nodes": [], "edges": []},
                    'results': []
                }
            }
    return message
