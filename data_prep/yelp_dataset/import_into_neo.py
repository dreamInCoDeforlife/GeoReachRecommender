"""
Creates the social and spatial graph in neo4j

For creating social graph we use user.json
For creating spatial graph we use business.json
For linking both these graphs we use review.json
"""

import json, time, gc
from py2neo import Graph
from py2neo.packages.httpstream import http
import os, secrets


def insert(graph, f, insert_query, unwind_key):
    entities = map(lambda x: json.loads(x), f.read().splitlines())
    print 'Completed JSON Loads at %s' % (time.time(),)
    x = 0
    while x < len(entities):
        graph.cypher.execute(insert_query, {unwind_key: entities[x:x + 200]})
        x = min(x + 200, len(entities))
        # print '\tSaved %d entities at %s' % (x, time.time())

    count = len(entities)
    entities = None  # for GC
    gc.collect(0)
    return count


def main(user, business, review, graph):
    """
    creates the graph as explained in the header of the file
    :param user: user JSON file path as string
    :param business: business JSON file path as string
    :param review: review JSON file path as string
    :param graph: open connection to graph DB
    :return: None
    """
    print 'Started at %s' % (time.time())

    # Create User Nodes
    with open(user, 'r') as u:
        insert_query = """
            UNWIND {users} as u
            CREATE (:Person {id: u['user_id'], name: u['name'], fans: u['fans'], elite: u['elite']});
            """
        num_users = insert(graph, u, insert_query, 'users')
        index_query = """
        CREATE INDEX ON :Person(id)
        """
        graph.cypher.execute(index_query)
        print '\tCreated %d Users Nodes by %s' % (num_users, time.time())

    # Create Business Nodes
    with open(business, 'r') as b:
        insert_query = """
            UNWIND {biz} as b
            CREATE (:Business {id: b['business_id'], name: b['name'], categories: b['categories']});
            """
        num_biz = insert(graph, b, insert_query, 'biz')
        index_query = """
        CREATE INDEX ON :Business(id)
        """
        graph.cypher.execute(index_query)
        print '\tCreated %d Business Nodes by %s' % (num_biz, time.time())

    # Create relationships between businesses and users
    with open(review, 'r') as r:
        insert_query = """
        UNWIND {rvw} as r
        MATCH (p:Person {id: r['user_id']}), (b:Business {id: r['business_id']})
        CREATE (p)-[:REVIEWED {stars: r['stars']}]->(b);
        """
        # TODO: Add votes info also to the reviews relationship - "votes": {"funny": 0, "useful": 0, "cool": 0}
        num_rel = insert(graph, r, insert_query, 'rvw')
        print '\tCreated %d Business-User relations by %s' % (num_rel, time.time())

    # Create relationships among users
    with open(user, 'r') as f:
        users = map(lambda x: json.loads(x), f.read().splitlines())
        friends = []
        for u in users:
            friends += [[u['user_id'], friend] for friend in u['friends']]
        users = None
        gc.collect(0)
        x = 0
        while x < len(friends):
            insert_query = """
            UNWIND {friends} as f
            MATCH (p:Person {id: f[0]}), (q:Person {id: f[1]})
            MERGE (p)-[:FRIEND]-(q);
            """
            graph.cypher.execute(insert_query, {"friends": friends[x:x + 1000]})
            x = min(x + 1000, len(friends))
        print '\tCreated %d relations at %s' % (len(friends), time.time())


if __name__ == '__main__':
    http.socket_timeout = 9999

    secrets.env()()  # set environment settings
    graph = Graph(os.environ['neo_db_url'])
    main('../dataset/user.json', '../dataset/business.json', '../dataset/review_train.json', graph)
