from github import GithubException


def create_action(repo, workflow_name, generator_path, branch_name, datetime):
    try:
        # Define the contents of the workflow file
        workflow_contents = f"""name: {workflow_name}

on:
  push:
    branches:
      - {branch_name}

jobs:
  generate-report:
    uses: ./.github/workflows/main.yml
    with:
      generator-path: {generator_path}
      output-path: ./
      # currently, this will be the date at which the tool is initially run (so leave blank for now and use action default)
      # time: {datetime}
"""
        # Create a new file in the .github/workflows directory with the workflow contents
        repo.create_file(
            path=f".github/workflows/{workflow_name}.yml",
            message=f"Add {workflow_name} GitHub Action workflow",
            content=workflow_contents,
            branch=branch_name,
        )

        print(f"Successfully added {workflow_name} workflow to {repo.name} repository!")

    except GithubException as e:
        print(f"Failed to add {workflow_name} workflow to {repo.name} repository.")
        print(e)
