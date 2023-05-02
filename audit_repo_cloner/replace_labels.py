


def delete_default_labels(repo):
    default_labels = [
        "bug", 
        "duplicate",
        "enhancement", 
        "invalid", 
        "question", 
        "wontfix", 
        "good first issue", 
        "help wanted", 
        "documentation"
    ]

    print("Deleting default labels...")
    for i in default_labels:
        try:
            label = repo.get_label(i)
            label.delete()
            print(f"Deleting {i}...")
        except:
            print(f"Label {i} does not exist. Skipping...")
            pass
    print("Finished deleting default labels")


def create_new_labels(repo):
    labels = [
        { "name": "Severity: Critical Risk", "color": "ff0000"},
        { "name": "Severity: High Risk" , "color": "B60205"},
        { "name": "Severity: Medium Risk" , "color": "D93F0B"},
        { "name": "Severity: Low Risk", "color": "FBCA04"},
        { "name": "Severity: Informational" , "color": "1D76DB"},
        { "name": "Severity: Gas Optimization", "color": "B4E197"},
        { "name": "Status: Open", "color": "5319E7"},
        { "name": "Status: Acknowledged", "color": "BFA8DC"},
        { "name": "Status: Resolved", "color": "0E8A16"},
        { "name": "Status: Closed", "color": "bfdadc"}
    ]

    print("Creating new labels...")
    for data in labels:
        try:
            repo.create_label(**data)
            # print(f"Creating new label {data}...")
        except:
            # print(f"Label {data} already exists. Skipping...")
            pass
    print("Finished creating new labels")


def replace_labels(repo):
    delete_default_labels(repo)
    create_new_labels(repo)
