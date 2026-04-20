import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict
import os

def extract_correct_runs(validator_files):
    correct_by_name = defaultdict(bool)

    for filename in validator_files:
        tree = ET.parse(filename)
        root = tree.getroot()

        for run in root.findall("run"):
            name = run.attrib.get("name")
            for col in run.findall("column"):
                if col.attrib.get("title") == "category" and col.attrib.get("value") == "correct":
                    correct_by_name[name] = True
                    break

    return correct_by_name

def validate_verifier(verifier_file, correct_by_name):
    tree = ET.parse(verifier_file)
    root = tree.getroot()

    for run in root.findall("run"):
        name = run.attrib.get("name")
        category_col = next((col for col in run.findall("column") if col.attrib.get("title") == "category"), None)
        if category_col is not None:
            if not correct_by_name.get(name, False) and category_col.attrib["value"] == "correct":
                category_col.attrib["value"] = "unkown"

    return tree

def main():
    parser = argparse.ArgumentParser(description="Validate BenchExec verifier XML using validator XMLs.")
    parser.add_argument("verifier", help="Verifier XML file (will be validated).")
    parser.add_argument("validators", nargs="+", help="One or more validator XML files.")
    parser.add_argument("-o", "--output", help="Output file name", default="validated.xml")
    args = parser.parse_args()

    print(f"Reading verifier result: {args.verifier}")
    print(f"Reading {len(args.validators)} validator(s): {', '.join(args.validators)}")

    correct_by_name = extract_correct_runs(args.validators)
    print(f"Found {len(correct_by_name)} inputs marked as 'correct' by validators.")

    validated_tree = validate_verifier(args.verifier, correct_by_name)

    validated_tree.write(args.output, encoding="utf-8", xml_declaration=True)
    print(f"Validated XML written to: {args.output}")

if __name__ == "__main__":
    main()
