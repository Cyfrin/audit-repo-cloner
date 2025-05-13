import logging

from github import Repository
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

# Set gql logging level to WARNING to suppress INFO logs
logging.getLogger("gql.transport.requests").setLevel(logging.WARNING)


def get_node_ids(client: Client, organization: str, target_repo_name: str, project_template_id: int) -> tuple[str, str, str]:
    query = gql(
        """
    query GetNodeIds($owner: String!, $repo_name: String!, $project_number: Int!) {
        repository(owner: $owner, name: $repo_name) {
            id
            owner {
                id
            }
        }
        organization(login: $owner) {
            projectV2(number: $project_number) {
                id
            }
        }
    }
    """
    )

    query_variables = {"owner": organization, "repo_name": target_repo_name, "project_number": project_template_id}

    try:
        response = client.execute(query, variable_values=query_variables)
        repo_node_id = response["repository"]["id"]
        org_node_id = response["repository"]["owner"]["id"]
        project_node_id = response["organization"]["projectV2"]["id"]
        # print(f"Node ID of the repository is: {repo_node_id}")
        # print(f"Node ID of the owner is: {org_node_id}")
        # print(f"Node ID of the project is: {project_node_id}")
        return repo_node_id, org_node_id, project_node_id
    except Exception as e:
        raise Exception(f"Error occurred while getting owner/repo node ids: {str(e)}")


def copy_project(client: Client, owner_node_id: str, project_template_id: str, project_title: str) -> str:
    # GraphQL Mutation for copying a project
    create_project_mutation = gql(
        """
        mutation CopyProjectV2($input: CopyProjectV2Input!) {
            copyProjectV2(input: $input) {
                projectV2 {
                    id
                    title
                }
            }
        }
    """
    )

    # Variables for the mutation
    copy_mutation_variables = {
        "input": {
            "ownerId": owner_node_id,
            "projectId": project_template_id,
            "title": project_title,
        }
    }

    try:
        # Execute the mutation
        response = client.execute(create_project_mutation, variable_values=copy_mutation_variables)
        project_id = response["copyProjectV2"]["projectV2"]["id"]
        project_title = response["copyProjectV2"]["projectV2"]["title"]
        print(f'Project "{project_title}" has been created successfully with id {project_id}')
        return project_id
    except Exception as e:
        raise Exception(f"Error occurred while copying the template project: {str(e)}")


def link_project_to_repo(client: Client, project_id: str, repo_node_id: str) -> str:
    # GraphQL Mutation for linking a project to a repo
    link_project_mutation = gql(
        """
        mutation LinkProjectV2ToRepository($input: LinkProjectV2ToRepositoryInput!) {
            linkProjectV2ToRepository(input: $input) {
                repository {
                    __typename
                }
            }
        }
    """
    )

    # Variables for the mutation
    link_mutation_variables = {
        "input": {
            "projectId": project_id,
            "repositoryId": repo_node_id,
        }
    }

    try:
        # Execute the mutation
        response = client.execute(link_project_mutation, variable_values=link_mutation_variables)
        print(f"Project with id {project_id} has been successfully linked to the repo.")
        return project_id
    except Exception as e:
        raise Exception(f"Error occurred while linking the project to the repo: {str(e)}")


def update_project(client: Client, target_repo_name: str, project_id: str, project_title: str):
    # GraphQL Mutation for updating a project
    update_project_mutation = gql(
        """
        mutation UpdateProjectV2($input: UpdateProjectV2Input!) {
            updateProjectV2(input: $input) {
                projectV2 {
                    __typename
                }
            }
        }
    """
    )

    project_description = f"A collaborative board for the {target_repo_name} audit"

    # Variables for the mutation
    update_mutation_variables = {
        "input": {
            "projectId": project_id,
            "public": False,
            "shortDescription": project_description,
        }
    }

    try:
        # Execute the mutation
        response = client.execute(update_project_mutation, variable_values=update_mutation_variables)

        # Check for errors
        if "errors" in response:
            error_messages = [error["message"] for error in response["errors"]]
            error_text = "\n".join(error_messages)
            raise Exception(f"GraphQL errors:\n{error_text}")
        else:
            print(f"Project {project_title} has been updated successfully")
    except Exception as e:
        raise Exception(f"Error occurred while updating the project board description: {str(e)}")


def clone_project(repo: Repository, github_token: str, organization: str, target_repo_name: str, project_template_id: str, project_title: str) -> str:
    """
    Clone a GitHub project from the template
        repo (Repository): GitHub repository object
        github_token (str): GitHub personal access token
        organization (str): GitHub organization name
        target_repo_name (str): Name of the repository with which the project will be associated
        project_template_id (str): ID of the project template, can be extracted from the link (e.g. https://github.com/orgs/Cyfrin/projects/5/views/1 => 5 is the ID)
        project_title (str): Name of the new project.

        Return the cloned project's ID, empty string on failure
    """

    try:
        repo.edit(has_projects=True)

        transport = RequestsHTTPTransport(
            url="https://api.github.com/graphql",
            headers={"Authorization": f"Bearer {github_token}"},
            use_json=True,
        )
        client = Client(transport=transport, fetch_schema_from_transport=False)

        repo_node_id, org_node_id, project_template_id = get_node_ids(client, organization, target_repo_name, int(project_template_id))

        if not repo_node_id or not org_node_id:
            raise Exception("Failed to get the repository or organization node ID.")

        project_node_id = copy_project(client, org_node_id, project_template_id, project_title)

        if not project_node_id:
            raise Exception("Failed to copy the project.")

    except Exception as e:
        raise Exception(f"Error occurred while cloning project: {str(e)}")

    try:
        # it doesn't matter if this call fails, we can still use the project as it is only a description update
        update_project(client, target_repo_name, project_node_id, project_title)
    except Exception as e:
        print(f"Error occurred while updating project: {str(e)}")

    try:
        # it doesn't matter if this call fails, we can still use the project as it is only a linking step
        link_project_to_repo(client, project_node_id, repo_node_id)
    except Exception as e:
        print(f"Error occurred while linking project to repo: {str(e)}")

    return project_node_id


def verify_project_exists(github_token: str, organization: str, project_title: str) -> bool:
    """
    Check if a project with the given title exists in the organization

    Args:
        github_token (str): GitHub personal access token
        organization (str): GitHub organization name
        project_title (str): Title of the project to look for

    Returns:
        bool: True if project exists, False otherwise
    """
    try:
        transport = RequestsHTTPTransport(
            url="https://api.github.com/graphql",
            headers={"Authorization": f"Bearer {github_token}"},
            use_json=True,
        )
        client = Client(transport=transport, fetch_schema_from_transport=False)

        # GraphQL query to get organization's projects
        query = gql(
            """
            query GetOrgProjects($org: String!, $first: Int!) {
                organization(login: $org) {
                    projectsV2(first: $first) {
                        nodes {
                            id
                            title
                            shortDescription
                        }
                    }
                }
            }
            """
        )

        # Variables for the query - get first 20 projects
        variables = {"org": organization, "first": 20}

        response = client.execute(query, variable_values=variables)

        # Check if the project exists
        for project in response.get("organization", {}).get("projectsV2", {}).get("nodes", []):
            if project_title in project.get("title", ""):
                print(f"Found project: {project['title']} (ID: {project['id']})")
                return True

        print(f"No project with title containing '{project_title}' found.")
        return False

    except Exception as e:
        print(f"Error occurred while verifying project existence: {str(e)}")
        return False
