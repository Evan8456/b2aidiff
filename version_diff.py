from os import getenv
from openai import OpenAI
import os
from dotenv import load_dotenv
from deepdiff import DeepDiff
import json
import argparse
import time
load_dotenv(".env", override=True)

def read_files_in_directory(root_folder):
    file_contents = {}

    # Walk through the folder and all sub-folders
    for dirpath, dirnames, filenames in os.walk(root_folder):
        for filename in filenames:
            # Construct the full file path
            file_path = os.path.join(dirpath, filename)
            relative_path = os.path.join(*file_path.split("/")[1:])


            try:
                # Open the file and read its contents
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_contents[relative_path] = file.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    return file_contents

def get_diff(json1, json2):
    diff = DeepDiff(json2, json1)
    return diff

def parse_order(order):
    filtered_order = order
    for i in range(len(order)):
        filtered_order[i] = filtered_order[i].split("/")[-1]
    return filtered_order

def conditions(properties):
    filtered_output= []
    filtered_condition = properties

    for j in filtered_condition:
        question = j["isAbout"].split("/")[-1]
        if "isVis" in j:
            vis = j["isVis"]
        else:
            vis = ""
        filtered_output.append({"question" : question, "condition": vis })

    return filtered_output


def filter_json(json):
    filtered_json = json
    json.pop("schemaVersion", None)
    json.pop("version", None)
    json.pop("@context", None)
    if "category" in json:
        repro_type = json["category"]
    elif "@type" in json:
        repro_type = json["@type"]
    elif "type" in json:
        repro_type = json["type"]

    try:
        if "Item" in repro_type:
            if "question" in json:
                if "responseOptions" in json:
                    option = json["responseOptions"]
                else:
                    option = ""
                filtered_json = {"question": json["question"], "Options": option, "type": "Item"}
            elif "preamble" in json:
                filtered_json = {"question": json["preamble"]["en"], "Options": json["responseOptions"], "type": "Item"}
        elif "Activity" in repro_type:
            order = parse_order(json["ui"]["order"])
            vis = conditions(json["ui"]["addProperties"])
            filtered_json = {"question_order": order, "conditions": vis, "type": "Activity"}
        else:
            print(json["id"])
    except:
        print(json)
    return filtered_json

def prompt_llm(prompt):
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=getenv("OPENROUTER_API_KEY"),
    )
    completion = client.chat.completions.create(
        model="openai/gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    if completion.choices is None:
        return None
    return completion.choices[0].message.content


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Passing in 2 versions of the protocol")
   
    # Add arguments for the folder paths
    parser.add_argument("new_protocol", type=str, help="Path to the first folder")
    parser.add_argument("old_protocol", type=str, help="Path to the second folder")
    args = parser.parse_args()
    mood_protocol_original = read_files_in_directory(args.new_protocol)
    redcap_protocol_original = read_files_in_directory(args.old_protocol)
    mood_protocol={}
    redcap_protocol = {}
    for key in mood_protocol_original.keys(): # mood
        value = json.loads(mood_protocol_original[key])
        mood_protocol[key] = filter_json(value)

    for key2 in redcap_protocol_original.keys(): #redcap
        value2 = json.loads(redcap_protocol_original[key2])
        redcap_protocol[key2] = filter_json(value2)

    missing = []
    questionnaire_prev = None
    for questionnaire in mood_protocol:
        
        i = questionnaire.replace("/", "-")
        count = 0
        with open('index.html', 'a') as file:
            if questionnaire in redcap_protocol:
                diff = (get_diff(mood_protocol[questionnaire], redcap_protocol[questionnaire]))
                questionnaire_file = questionnaire.split("/")[-1]
                questionnaire_curr = questionnaire.split("/")[0]
                
                if diff != {}:
                    #print(mood_protocol[questionnaire])
                    if "Item" in mood_protocol[questionnaire]["type"]:
                        #time.sleep(10)
                        output = prompt_llm(f"You are given a diff of 2 different versions of the questionnaire json. \
                            we only care about the question, and responseOptions if present. give me a human readable \
                                version of the following diff, list all changes related  question, and \
                                    responseOptions given {diff}. Please return in the following format, Added: , Changed, \
                                        Removed. Theses diffs reflect changes to a questionnaire, only summarize how the \
                                            questionnaire questions has changed.")
                        while output is None and count <5:
                            count += 1
                            time.sleep(10)
                            output = prompt_llm(f"You are given a diff of 2 different versions of the questionnaire json. \
                            we only care about the question, and Options if present. give me a human readable \
                                version of the following diff, list all changes related  question, and \
                                    responseOptions given {diff}. Please return in the following format, Question Changed: ,Choices Added: ,Choices Changed: \
                                       Choices RemovedL Theses diffs reflect changes to a questionnaire, only summarize how the \
                                            questionnaire questions has changed.")
                        if questionnaire_curr != questionnaire_prev:
                            file.write(f"<h2>{questionnaire_file}</h2>")
                            questionnaire_prev = questionnaire_curr
                        file.write(f"<div>  <a href='./individual-file-diffs/{i}.html'> <h3>{questionnaire_file}</h3> </a>")
                        file.write(f"<pre>{output}</pre> </div>")
                    elif  "Activity" in mood_protocol[questionnaire]["type"]:
                        output = prompt_llm(f"You are given a diff of 2 different versions of the questionnaire json. \
                            we only care about the question_order and the conditions if present. give me a human readable \
                                version of the following diff, list all changes related to question_order, and \
                                    conditions related to the question given {diff}. Please return in the following format,  Order Changed, \
                                        Removed. Theses diffs reflect changes to a questionnaire, only summarize how the \
                                            The following isVis changed for the following question.")
                        if questionnaire_curr != questionnaire_prev:
                            file.write(f"<h2>{questionnaire_file}</h2>")
                            questionnaire_prev = questionnaire_curr
                        file.write(f"<div>  <a href='./individual-file-diffs/{i}.html'> <h3>{questionnaire_file}</h3> </a>")
                        file.write(f"<pre>{output}</pre> </div>")
            else:
                # file.write( f"<p>{questionnaire}  is not present in the redcap protocol</p>")
                missing.append(questionnaire)
    
    with open('missing.html', 'a') as file:     
        for i in missing:
            file.write( f"<p>{i} is not present in the redcap protocol</p>")
            
            

        
