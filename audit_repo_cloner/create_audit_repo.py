import os
import shutil
from datetime import date
from github import Github, GithubException
from dotenv import load_dotenv
from copy_issue_template import copy_issue_template
from replace_labels import replace_labels
from create_action import create_action

load_dotenv()

TOKEN = os.getenv("TOKEN")
ORGANIZATION = os.getenv("ORGANIZATION")

def copy_files_recursive(source_repo, repo, commit_message, path=""):
    for file in source_repo.get_contents(path):
        if file.type == "file":
            print(f"Copying {file.path}...")
            if file.name == "README.md":
                repo.update_file(file.path, commit_message, file.decoded_content, repo.get_contents("README.md").sha)
            else:
                if file.decoded_content is not None:
                    repo.create_file(file.path, commit_message, file.decoded_content)
                else:
                    print(f"Skipping {file.path} (unsupported encoding)")
        elif file.type == "dir":
            print(f"Copying {file.path}...")
            copy_files_recursive(source_repo, repo, commit_message, file.path)

def main():
    # Prompt user for input
    print("Hello! This script will clone target repository and prepare it for a Cyfrin audit. Please enter the following details:\n")
    while True:
        # source_username = input("1) Source repo owner username: ")
        # source_repo_name = input("2) Source repo name: ")
        # source_repo_branch = input("3) Source repo branch: ")
        # repo_name = input("4) New repo name: ")
        source_url = input("1) Source repo url: ")
        # Remove the .git extension if it exists
        source_url = source_url.rstrip(".git")

        # Split the URL by "/"
        url_parts = source_url.split("/")

        # Extract the username and repo name from the URL
        source_username = url_parts[-2]
        source_repo_name = url_parts[-1]
        
        source_repo_branch = "main"
        auditors = input("2) Enter the names of the auditors (separated by spaces): ")

        if source_username and source_repo_name and source_repo_branch and auditors:
            auditors = [a.strip() for a in auditors.split(" ")]
            break
        print("Please fill in all the details.")

    # Create new repository using PyGithub
    g = Github(TOKEN)
    org = g.get_organization(ORGANIZATION)

    try:
        repo = g.get_repo(f"{ORGANIZATION}/{source_repo_name}")
    except GithubException as e:
        if e.status == 404:
            repo = None
        else:
            print(f"Error checking if repository exists: {e}")
            exit()

    if repo is None:
        try:
            repo = org.create_repo(source_repo_name, private=True)
        except GithubException as e:
            if e.status == 403:
                print("Error creating repository: You do not have the necessary permissions to create a repository. Please make sure your token has the 'repo' scope.")
            else:
                print(f"Error creating repository: {e}")
            exit()

        # Clone the source repo and create new repo
        try:
            print(f"Cloning {source_repo_name}...")

            os.chdir("/tmp")
            os.system(f"git clone https://github.com/{source_username}/{source_repo_name}.git {source_repo_name}")
            os.chdir(source_repo_name)
            os.system("git commit -m 'initial commit")
            os.system(f"git remote set-url origin https://github.com/{ORGANIZATION}/{source_repo_name}.git")
            os.system("git push -u origin main")
        
        except GithubException as e:
            print(f"Error cloning repository: {e}")
            repo.delete()
            exit()

    # Copy issue template to new repo and replace labels
    copy_issue_template(repo)
    replace_labels(repo)

    # Loop through the list of auditors and create a new branch for each
    main_branch = repo.get_branch("main")
    for auditor in auditors:
        branch_name = f"audit/{auditor}"
        try:
            repo.create_git_ref(f"refs/heads/{branch_name}", main_branch.commit.sha)
        except GithubException as e:
            if e.status == 422:
                print(f"Branch {branch_name} already exists. Skipping...")
                continue
            else:
                print(f"Error creating branch: {e}")
                exit()

    # Create a new report branch on the new repo
    branch_name = "report"
    try:
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
    except GithubException as e:
        if e.status == 422:
            print(f"Branch {branch_name} already exists. Skipping...")
        else:
            print(f"Error creating branch: {e}")
            exit()

    # Add report-generator-template as a subtree
    subtree_path_prefix = "cyfrin-report"
    subtree_name = "report-generator-template"
    subtree_path = f"{subtree_path_prefix}/{subtree_name}"
    subtree_url = "https://github.com/ChainAccelOrg/report-generator-template.git"
    try:
        print(f"Adding subtree {subtree_name}...")

        # Pull the latest changes from the origin
        os.chdir(f"/tmp/{source_repo_name}")
        os.system(f"git pull origin {branch_name} --rebase")
        os.system(f"git checkout {branch_name}")

        # Add the subtree to the repo
        os.system(f"git subtree add --prefix {subtree_path} {subtree_url} main --squash")
        os.system("mkdir .github/workflows")
        os.system(f"mv {subtree_path}/.github/workflows/main.yml .github/workflows/main.yml")

        # Commit the changes
        os.system(f"git add .")
        os.system(f"git commit -m 'install: {subtree_name}'")

        # Push the changes back to the origin
        os.system(f"git push")

        # Remove the local directory
        os.chdir("..")
        shutil.rmtree(source_repo_name)
        
        print(f"The subtree {subtree_name} has been added to {repo.name} on branch {branch_name}")

    except GithubException as e:
        print(f"Error adding subtree: {e}")
        exit()


    # Set up CI for report generation
    try:
        create_action(repo, "generate-report", subtree_path, branch_name, str(date.today()))
    except Exception as e:
        print(f"Error occurred while setting up CI: {str(e)}")
        print("Please set up CI manually using the report-generation.yml file.")
    else:
        print("CI for report generation has been set up successfully!")

    # Set up project board for collaboration
    try:
        repo.edit(has_projects=True)
        project = repo.create_project(f"{source_username}/{source_repo_name}", body=f"A collaborative board for the {source_username}/{source_repo_name} audit")
        column_names = ["Archive", "Ideas", "Findings", "Peer Reviewed", "Report"]
        labels = ["Archived", "Needs Discussion", "Self-Validated", "Co-Validated", "Report Ready"]
        columns = [project.create_column(name) for name in column_names]
        status_field = project.create_custom_field(name="Status", type="dropdown", possible_values=labels)
        poc_field = project.create_custom_field(name="PoC", type="boolean")

        # Define the column-to-label mapping
        column_to_label_mapping = {column: label for column, label in zip(columns, labels)}

        # Define the workflow action
        def handle_card_move(event):
            card = event.project_card
            column = card.column
            label = column_to_label_mapping.get(column)
            if label:
                issue = card.get_content()
                issue.add_to_labels(label)

        # Register the workflow
        project.add_to_event_handlers("project_card_move", handle_card_move)
        print("Project board has been set up successfully!")
    except Exception as e:
        print(f"Error occurred while setting up project board: {str(e)}")
        print("Please set up project board manually.")

    print("Done!")

if __name__ == "__main__":
    main()
