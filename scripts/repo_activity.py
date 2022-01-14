# Copyright 2022 VMware, Inc.
# SPDX-License-Identifier: BSD-2-Clause

"""Repo Activity GraphQL Version
This script uses the GitHub GraphQL API to retrieve relevant
information about all repositories from one or more GitHub
orgs.

As input, this script requires a file named 'orgs.txt' containing
the name of one GitHub org per line residing in the same folder 
as this script.

Your API key should be stored in a file called gh_key in the
same folder as this script.

This script requires that `pandas` be installed within the Python
environment you are running this script in.

As output:
* A message about each org being processed will be printed to the screen.
* the script creates a csv file stored in an subdirectory
  of the folder with the script called "output" with the filename in 
  this format with today's date.

output/a_repo_activity_2022-01-14.csv"
"""

import sys
import pandas as pd
import csv
from datetime import datetime
from time import sleep
from os.path import dirname, join
from common_functions import read_key

def make_query(after_cursor = None):
    return """query RepoQuery($org_name: String!) {
             organization(login: $org_name) {
               repositories (first: 100 after: AFTER){
                 pageInfo {
                   hasNextPage
                   endCursor
                 }
                 nodes { 
                   nameWithOwner
                   name
                   licenseInfo {
                     name
                   }
                   isPrivate
                   isFork
                   isEmpty
                   isArchived
                   forkCount
                   stargazerCount
                   createdAt
                   updatedAt
                   pushedAt
                   defaultBranchRef {
                     name 
                     target{
                        ... on Commit{
                            history(first:1){
                        edges{
                            node{
                                ... on Commit{
                                    committedDate
                                    author{
                                      name
                                      email
                                      user{
                                        login
                                      }
                                    }
                            }
                        }
                    }
                }
                   }
                 }
               }
              }
              }
              }
            }""".replace(
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
    )

# Read GitHub key from file
try:
    api_token = read_key('gh_key')

except:
    print("Error reading GH Key. Exiting")
    sys.exit()

def get_repo_data(api_token):
    import requests
    import json
    import pandas as pd

    url = 'https://api.github.com/graphql'
    headers = {'Authorization': 'token %s' % api_token}
    
    repo_info_df = pd.DataFrame()
    
    org_list = ["cncf","knative"]
    
    # Read list of orgs from a file

    org_list = []
    with open('orgs.txt') as orgfile:
        orgs = csv.reader(orgfile)
        for row in orgs:
            org_list.append(row[0])
    
    for org_name in org_list:  
        has_next_page = True
        after_cursor = None
    
        print("Processing", org_name)

        while has_next_page:

            try:
                query = make_query(after_cursor)

                variables = {"org_name": org_name}
                r = requests.post(url=url, json={'query': query, 'variables': variables}, headers=headers)
                json_data = json.loads(r.text)

                df_temp = pd.DataFrame(json_data['data']['organization']['repositories']['nodes'])
                repo_info_df = repo_info_df.append(df_temp, ignore_index=True)

                has_next_page = json_data["data"]["organization"]["repositories"]["pageInfo"]["hasNextPage"]

                after_cursor = json_data["data"]["organization"]["repositories"]["pageInfo"]["endCursor"]
            except:
                has_next_page = False
                print("ERROR Cannot process", org_name)
        
    return repo_info_df

repo_info_df = get_repo_data(api_token)

# This section reformats the output into what we need in the csv file

repo_info_df["org"] = repo_info_df["nameWithOwner"].str.split('/').str[0]

def expand_license(license):
    if pd.isnull(license):
        license_name = 'Likely Missing'
    else:
        license_name = license['name']
    return license_name

repo_info_df['license'] = repo_info_df['licenseInfo'].apply(expand_license)
repo_info_df = repo_info_df.drop(columns=['licenseInfo'])

def expand_commits(commits):
    if pd.isnull(commits):
        commits_list = [None, None, None, None]
    else:
        node = commits['target']['history']['edges'][0]['node']
        try:
            commit_date = node['committedDate']
        except:
            commit_date = None
        try:
            author_name = node['author']['name']
        except:
            author_name = None
        try:
            author_email = node['author']['email']
        except:
            author_email = None
        try:
            author_login = node['author']['user']['login']
        except:
            author_login = None
        commits_list = [commit_date, author_name, author_email, author_login]
    return commits_list

repo_info_df['commits_list'] = repo_info_df['defaultBranchRef'].apply(expand_commits)
repo_info_df[['last_commit_date','author_name','author_email', 'author_login']] = pd.DataFrame(repo_info_df.commits_list.tolist(), index= repo_info_df.index)
repo_info_df = repo_info_df.drop(columns=['commits_list','defaultBranchRef'])

repo_info_df = repo_info_df[['org','name','nameWithOwner','license','isPrivate','isFork','isArchived', 'forkCount', 'stargazerCount', 'isEmpty', 'createdAt', 'updatedAt','pushedAt','last_commit_date','author_login','author_name','author_email']] 

# prepare file and write dataframe to csv

try:
    today = datetime.today().strftime('%Y-%m-%d')
    output_filename = "./output/a_repo_activity_" + today + ".csv"
    current_dir = dirname(__file__)
    file_path = join(current_dir, output_filename)
    repo_info_df.to_csv(file_path, index=False)

except:
    print('Could not write to csv file. Exiting')