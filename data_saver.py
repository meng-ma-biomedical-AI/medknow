#!/usr/bin/python !/usr/bin/env python
# -*- coding: utf-8 -*


# Functions to extract knowledge from medical text. Everything related to 
# reading, parsing and extraction needed for the knowledge base. Also,
# some wrappers for SemRep, MetaMap and Reverb.

import json
import os
import py2neo
import csv
import subprocess
import urllib2
import requests
import unicodecsv as csv2
import pandas as pd
import py2neo
from config import settings
from utilities import time_log




def save_json(json_):
    """
    Helper function to save enriched medical json to file.
    Input:
        - json_: dic,
        json-style dictionary generated from the extractors in the
        previous phase
    """

    # Output file location from settings
    outfile = settings['out']['json']['out_path']
    with open(outfile, 'w+') as f:
        json.dump(json_, f, indent=3)



def save_csv(json_):
    """
    Helper function to save enriched medical json to file.
    Input:
        - json_: dic,
        json-style dictionary generated from the extractors in the
        previous phase
    """

    # Output file location from settings
    outfile = settings['out']['json']['out_path']
    with open(outfile, 'w+') as f:
        json.dump(json_, f, indent=3)



def save_neo4j(json_):
    """
    Helper function to save enriched medical json to file.
    Input:
        - json_: dic,
        json-style dictionary generated from the extractors in the
        previous phase
    """

    # Output file location from settings
    outfile = settings['out']['json']['out_path']
    with open(outfile, 'w+') as f:
        json.dump(json_, f, indent=3)

def aggregate_mentions(entity_pmc_edges):
    """
    Function to aggregate recurring entity:MENTIONED_IN:pmc relations.
    Input:
        - entity_pmc_edges: list,
        list of dicts as generated by create_neo4j_ functions
    Outpu:
        - entity_pmc_edges: list,
        list of dicts with aggregated values in identical ages
    """
    uniques = {}
    c = 0
    for edge in entity_pmc_edges:
        cur_key = str(edge[':START_ID'])+'_'+str(edge[':END_ID'])
        flag = False
        if cur_key in uniques:
            uniques[cur_key]['score:float[]'] = uniques[cur_key]['score:float[]']+';'+edge['score:float[]']
            uniques[cur_key]['sent_id:string[]'] = uniques[cur_key]['sent_id:string[]']+';'+edge['sent_id:string[]']
            flag = True
        else:
            uniques[cur_key] = edge
        if flag:
            c += 1
    un_list = []
    time_log('Aggregated %d mentions from %d in total' % (c, len(entity_pmc_edges)))
    for k, v in uniques.iteritems():
        un_list.append(v)
    return un_list


def aggregate_relations(relations_edges):
    """
    Function to aggregate recurring entity:SEMREP_RELATION:entity relations.
    Input:
        - relations_edges: list,
        list of dicts as generated by create_neo4j_ functions
    Outpu:
        - relations_edges: list,
        list of dicts with aggregated values in identical ages
    """
    uniques = {}
    c = 0
    for edge in relations_edges:
        cur_key = str(edge[':START_ID'])+'_'+str(edge[':TYPE'])+'_'+str(edge[':END_ID'])
        flag = False
        if cur_key in uniques:
            if not(edge['sent_id:string[]'] in uniques[cur_key]['sent_id:string[]']):
                for field in edge.keys():
                    if not(field in [':START_ID', ':TYPE', ':END_ID']):
                        uniques[cur_key][field] = uniques[cur_key][field]+';'+edge[field]
                flag = True
        else:
            uniques[cur_key] = edge
        if flag:
            c += 1
    un_list = []
    time_log('Aggregated %d relations from %d in total' % (c, len(relations_edges)))
    for k, v in uniques.iteritems():
        un_list.append(v)
    return un_list


def create_neo4j_results(json_, key='harvester'):
    """
    Helper function to call either the create_neo4j_harvester or the
    create_neo4j_edges function, according to the type of input.
    Input:
        - json_: dic,
        dictionary-json style generated from the parsers/extractors in the
        previous stages
        - key: str,
        string for denoting which create_neo4j_ function to use
    Output:
        - results: dic,
        json-style dictionary with keys 'nodes' and 'edges' containing
        a list of the transformed nodes and edges to be created/updated in
        neo4j. Each element in the list has a 'type' field denoting the type
        of the node/edge and the 'value' field containg the nodes/edges
    """
    if key == 'harvester':
        results = create_neo4j_harvester(json_)
    elif key == 'edges':
        results = create_neo4j_edges(json_)
    else:
        print('Type %s of data not yet supported!' % key)
        raise NotImplementedError
    return results

def create_neo4j_edges(json_):
    """
    Function that takes the edges file as provided and generates the nodes
    and relationships entities needed for creating/updating the neo4j database.
    Currently supporting: 
        - Nodes: ['Articles(PMC)', 'Entities(MetaMapConcepts)'] 
        - Edges: ['Relations between Entities']
    Input:
        - json_: dic,
        json-style dictionary generated from the parser in the
        previous phase
    Output:
        - results: dic,
        json-style dictionary with keys 'nodes' and 'edges' containing
        a list of the transformed nodes and edges to be created/updated in
        neo4j. Each element in the list has a 'type' field denoting the type
        of the node/edge and the 'value' field containg the nodes/edges
    """
    edgefield = settings['load']['edges']['edge_file']
    for edge in json_[edgefield]:
        #pass

        results = {'nodes': [{'type': 'Entity', 'values': entities_nodes}, {'type': 'Article', 'values': articles_nodes}],
               'edges': [{'type': 'relation', 'values': relations_edges}, {'type': 'mention', 'values': entity_pmc_edges}]
               }

def create_neo4j_harvester(json_):
    """
    Function that takes the enriched json_ file and generates the nodes
    and relationships entities needed for creating/updating the neo4j database.
    Currently supporting: 
        - Nodes: ['Articles(PMC)', 'Entities(MetaMapConcepts)', 'MESH(Headings)'] 
        - Edges: ['Relations between Entities', 'Entity:MENTIONED_IN:Article'
                  'Entiy:HAS_MESH:MESH']
    Input:
        - json_: dic,
        json-style dictionary generated from the extractors in the
        previous phase
    Output:
        - results: dic,
        json-style dictionary with keys 'nodes' and 'edges' containing
        a list of the transformed nodes and edges to be created/updated in
        neo4j. Each element in the list has a 'type' field denoting the type
        of the node/edge and the 'value' field containg the nodes/edges
    """
    # docfield containing list of elements
    out_outfield = settings['out']['json']['json_doc_field']
    # textfield to read text from
    out_textfield = settings['out']['json']['json_text_field']
    # idfield where id of document is stored
    out_idfield = settings['out']['json']['json_id_field']
    # labelfield where the label is located
    out_labelfield = settings['out']['json']['json_label_field']

    entities_nodes = []
    unique_sent = {}
    articles_nodes = []
    entity_pmc_edges = []
    relations_edges = []
    unique_cuis = []
    #cui_to_mesh_path = settings['load']['mesh']['path']
    #with open(cui_to_mesh_path, 'r') as f:
    #    mapping = json.load(f)['cuis']
    for doc in json_[out_outfield]:
        pmid = doc[out_idfield]
        tmp_sents = []
        #doc_mesh = []
        for sent in doc['sents']:
            cur_sent_id = str(pmid)+'_'+sent['sent_id']
            tmp_sents.append(cur_sent_id)
            unique_sent[cur_sent_id] = sent['sent_text']
            for ent in sent['entities']:
                if ent['cuid']:
                    #if (ent['cuid'] in mapping):
                    #    doc_mesh.append(ent['cuid'])
                    #    cur_map = mapping[ent['cuid']]
                    #    for i, id_ in enumerate(cur_map['ids']):
                    #        if not(id_ in unique_mesh):
                    #            unique_mesh.append(id_)
                    #            mesh_nodes.append({'mesh_id:ID': id_, 'label': cur_map['labels'][i]})
                    if ent['cuid'] in unique_cuis:
                        continue
                    else:
                        unique_cuis.append(ent['cuid'])
                        if (type(ent['sem_types']) == list and len(ent['sem_types']) > 1):
                            sem_types = ';'.join(ent['sem_types'])
                        elif (',' in ent['sem_types']):
                            sem_types = ';'.join(ent['sem_types'].split(','))
                        else:
                            sem_types = ent['sem_types']
                        #if not(ent['cuid']):
                        entities_nodes.append({'cui:ID': ent['cuid'], 
                                         'label': ent['label'], 
                                         'sem_types:string[]': sem_types})
                    entity_pmc_edges.append({':START_ID': ent['cuid'],
                                             'score:float[]': ent['score'],
                                             'sent_id:string[]': cur_sent_id,
                                             ':END_ID': pmid})
            for rel in sent['relations']:
                if rel['subject__cui'] and rel['object__cui']:
                    relations_edges.append({':START_ID': rel['subject__cui'],
                                     'subject_score:float[]': rel['subject__score'],
                                     'subject_sem_type:string[]': rel['subject__sem_type'],
                                     ':TYPE': rel['predicate'].replace('(','__').replace(')','__'),
                                     'pred_type:string[]': rel['predicate__type'],
                                     'object_score:float[]': rel['object__score'],
                                     'object_sem_type:string[]': rel['object__sem_type'],
                                     'sent_id:string[]': cur_sent_id,
                                     'negation:string[]': rel['negation'],
                                     ':END_ID': rel['object__cui']})            
        articles_nodes.append({'pmcid:ID': doc[out_idfield], 
                               'title': doc[out_labelfield], 
                               'journal': doc['journal'], 
                                'sent_id:string[]': ';'.join(tmp_sents)})
        #for doc_cui in doc_mesh:
        #    try:
        #        cur_map = mapping[doc_cui]
        #        for id_ in cur_map['ids']:
        #            pmc_mesh_edges.append({':START_ID': doc['pmid'], 
        #                           ':TYPE': 'HAS_MESH', 
        #                            ':END_ID':id_})
        #    except KeyError:
        #        continue
    entity_pmc_edges = aggregate_mentions(entity_pmc_edges)
    relations_edges = aggregate_relations(relations_edges)
    results = {'nodes': [{'type': 'Entity', 'values': entities_nodes}, {'type': 'Article', 'values': articles_nodes}],
               'edges': [{'type': 'relation', 'values': relations_edges}, {'type': 'mention', 'values': entity_pmc_edges}]
               }
    return results


def create_neo4j_csv(results):
    """
    Create csv's for use by the neo4j import tool. Relies on create_neo4j_ functions
    output and transforms it to suitable format for automatic importing.
    Input: 
        - results: dic,
        json-style dictionary. Check create_neo4j_ function output for
        details
    Output:
        - None just saves the documents in the allocated path as defined
        in settings.yaml 
    """
    outpath = settings['out']['csv']['out_path']
    entities_nodes = None
    articles_nodes = None
    relations_edges = None
    entity_pmc_edges = None
    for nodes in results['nodes']:
        if nodes['type'] == 'Entity':
            entities_nodes = nodes['values']
        elif nodes['type'] == 'Article':
            articles_nodes = nodes['values']
    for edges in results['edges']:
        if edges['type'] == 'relation':
            relations_edges = edges['values']
        elif edges['type'] == 'mention':
            entity_pmc_edges = edges['values']

    dic_ = {
        'entities.csv': entities_nodes,
        'articles.csv': articles_nodes,
        'entities_pmc.csv':entity_pmc_edges, 
        'relations.csv':relations_edges,
    }

    dic_fiels = {
        'entities.csv': ['cui:ID', 'label', 'sem_types:string[]'],
        'articles.csv': ['pmcid:ID', 'title', 'journal','sent_id:string[]'],
        #'mesh.csv':['mesh_id:ID', 'label'],
        'entities_pmc.csv':[':START_ID','score:float[]','sent_id:string[]', ':END_ID'], 
        'relations.csv':[':START_ID','subject_score:float[]','subject_sem_type:string[]',':TYPE','pred_type:string[]', 'object_score:float[]','object_sem_type:string[]','sent_id:string[]','negation:string[]',':END_ID'],
        #'pmc_mesh.csv': [':START_ID',':TYPE', ':END_ID']
    }

    for k, toCSV in dic_.iteritems():
        if toCSV:
            keys = toCSV[0].keys()
            out = os.path.join(outpath, k)
            with open(out, 'wb') as output_file:
                time_log("Created file %s" % k)
                dict_writer = csv2.DictWriter(output_file, fieldnames=dic_fiels[k], encoding='utf-8')
                dict_writer.writeheader()
                dict_writer.writerows(toCSV)
        time_log('Created all documents needed')



def fix_on_create_nodes(node):
    """
    Helper function to create the correct cypher string for
    querying and merging a new node to the graph. This is used
    when no node is matched and a new one has to be created.
    Input:
        - node: dic,
        dictionary of a node generated from some create_neo4j_
        function
    Output:
        - s: string,
        string of cypher query handling the merging new node task
    """
    s = 'ON CREATE SET'
    for key, value in node.iteritems():
        if 'ID' in key.split(':'):
            continue
        elif 'string[]' in key:
            field = key.split(':')[0]
            string_value = '['
            for i in value.split(';'):
                string_value  += '"'+ i + '"' + ','
            string_value  = string_value [:-1]+ ']'
            s += ' a.%s = %s,' %(field, string_value )
        elif 'float[]' in key:
            field = key.split(':')[0]
            string_value = str([int(i) for i in value.split(';')])
            s += ' a.%s = %s,' %(field, string_value)
        else:
            field = key.split(':')[0]
            s += ' a.%s = "%s",' %(field, value)
    s = s[:-1]
    return s

def create_merge_query(node, type_, id_):
    """
    Creating the whole merge and update cypher query for a node.
    Input:
        - node: dic,
        dictionary of a node containing the attributes of the
        node
        - type_: str,
        ty
    """
    quer = """
    MERGE (a:%s {%s:"%s"})
    %s""" % (type_, id_, node[id_+":ID"], fix_on_create(node))
    return quer



def update_neo4j(results):
    
    """
    Function to create/update a neo4j database according to the nodeg and edges
    generated by the create_neo4j_ functions. Change settings.yaml values in
    the neo4j group of variables to match your needs.
    Input:
        - results: 
        json-style dictionary. Check create_neo4j_ functions output for
        details
    Output: None, creates/merges the nodes to the wanted database
    """
    host = settings['neo4j']['host']
    port = settings['neo4j']['port']
    user = settings['neo4j']['user']
    password = settings['neo4j']['password']
    try:
        graph = py2neo.Graph(host=host, port=port, user=user, password=pass)
    except Exception, e:
        print Exception, e
        print("Couldn't connect to db! Check settings!")
        exit(2)
    graph_new = py2neo.Graph()
