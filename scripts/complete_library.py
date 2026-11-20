"""Reparar duas importações específicas e conservar a proveniência dos recursos."""
import hashlib
import json
from import_research_library import ROOT, fetch, import_reference


def main():
    catalog_path = ROOT / 'config' / 'skills_catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    for index, entry in enumerate(catalog['entries']):
        if entry['id'] == 'agentscope-ai-bib-verify':
            catalog['entries'][index] = import_reference(entry['reference'])
        if entry['id'] == 'dougtrajano-arxiv-search':
            resource = 'scripts/arxiv_search.py'
            url = 'https://raw.githubusercontent.com/DougTrajano/pydantic-ai-skills/HEAD/examples/skills/arxiv-search/' + resource
            raw = fetch(url)
            target = ROOT / 'skills' / 'imported' / entry['id'] / resource
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            if resource not in entry['files']:
                entry['files'].append(resource)
            entry['resource_hashes'] = {resource: hashlib.sha256(raw).hexdigest()}
            (target.parent.parent / 'source.json').write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding='utf-8')
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    print({status: sum(e['status'] == status for e in catalog['entries']) for status in ['imported', 'reference_only']})


if __name__ == '__main__':
    main()
