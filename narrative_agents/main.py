from pepnarrativeagent import PEPAgent

def main():
    print("Hello from pepagent!")
    pep_ar_file = "/domino/datasets/local/CoreRulerLangraph/pep_client.txt"
    with open(pep_ar_file, "r") as f:
        pep_ar = f.read()
    pep_profile_file = "/domino/datasets/local/CoreRulerLangraph/pep_profile.txt"
    with open(pep_profile_file, "r") as f:
        pep_profile = f.read()

    initial_request = {"pep_ar": pep_ar, "pep_profile": pep_profile}

    agent = PEPAgent()
    result = agent.invoke(initial_request)
    print(result)

if __name__ == "__main__":
    main()
