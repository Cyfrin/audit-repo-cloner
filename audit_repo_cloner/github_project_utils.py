import json
import os
import requests

def get_organization_node_id(token: str, org_name: str)->str:
    """
    Get the GitHub organization's node id to use for later call to GraphQL
        token (str): GitHub personal access token
        org_name (str): GitHub organization name (username)

        Return the node ID of the organization, empty string on failure
    """
    url = f"https://api.github.com/users/{org_name}"

    payload = {}
    headers = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github+json'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    res = response.json()
    return res.get('node_id', '')

def get_project_node_id(token: str, org_name:str, project_template_id: str)->str:
    """
    Get the GitHub organization's node id to use for later call to GraphQL
        token (str): GitHub personal access token
        org_name (str): GitHub organization name (username)
        project_template_id (str): ID of the project template, can be extracted from the link (e.g. https://github.com/orgs/KupiaSec/projects/7/views/2 => 7 is the ID)

        Return the node ID of the project, empty string on failure
    """
     # get the project ID
    url = "https://api.github.com/graphql"
    payload = "{\"query\":\"query{organization(login: \\\""+org_name+"\\\") {projectV2(number: "+project_template_id+"){id}}}\",\"variables\":{}}"
    headers = {
        'Authorization': f'token {token}',
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    res = response.json()
    return res.get('data', {}).get('organization', {}).get('projectV2', {}).get('id', '')


def clone_project(token: str, org_name: str, project_template_id:str, project_title:str = '')->str:
    """
    Clone a GitHub project from the template
        token (str): GitHub personal access token
        org_node_id (str): GitHub Organization node ID (can be retrieved by calling get_organization_node_id)
        project_template_id (str): ID of the project template, can be extracted from the link (e.g. https://github.com/orgs/Cyfrin/projects/7/views/2 => 7 is the ID)
        project_title (Optional[str]): Name of the new project, if empty 'CLONED PROJECT' will be used.

        Return the cloned project's ID, empty string on failure
    """
    if not org_name or not project_template_id:
        return

    if not project_title:
        project_title = 'CLONED PROJECT'

    # get the organization node id
    org_node_id = get_organization_node_id(token, org_name)
    if not org_node_id:
        print('Failed to get the organization node ID.')
        return

    # get the project node id
    project_node_id = get_project_node_id(token, org_name, project_template_id)

    # clone the project
    url = "https://api.github.com/graphql"
    payload = '{"query":"mutation {copyProjectV2(input: {ownerId: \\\"' + org_node_id + '\\\" projectId: \\\"' + project_node_id + '\\\" title: \\\"' + project_title + '\\\"}) {projectV2 {id}}}\","variables":{}}'
    headers = {
        'Authorization': f'token {token}',
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    res = response.json()
    return res.get('data', {}).get('organization', {}).get('projectV2', {}).get('id', '')



