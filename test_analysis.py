from api.models_db.parsed_text import ParsedDocument, DocumentAnalysis
import requests
import json

# Get all documents with analysis
docs_with_analysis = ParsedDocument.objects.filter(analysis__isnull=False)
print(f'Documents with analysis: {len(docs_with_analysis)}')

for doc in docs_with_analysis:
    print(f'\nDocument {doc.id} -> Analysis {doc.analysis.id}')
    
    # Test the analysis endpoint
    response = requests.get(f'http://localhost:8000/api/documents/{doc.id}/analysis/')
    if response.status_code == 200:
        data = response.json()
        print(f'  API returns analysis ID: {data.get("id")}')
        print(f'  Has analysis data: {"analysis" in data}')
        
        # Test translation
        analysis_id = data.get('id')
        if analysis_id:
            for lang in ['hi', 'ta']:
                trans_response = requests.get(f'http://localhost:8000/api/analysis/{analysis_id}/translations/{lang}/')
                if trans_response.status_code == 200:
                    print(f'  {lang} translation: EXISTS')
                elif trans_response.status_code == 404:
                    # Try to create
                    create_response = requests.post(
                        f'http://localhost:8000/api/analysis/{analysis_id}/translate/',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps({'language': lang})
                    )
                    if create_response.status_code == 200:
                        print(f'  {lang} translation: CREATED')
                    else:
                        print(f'  {lang} translation: FAILED ({create_response.status_code})')
                else:
                    print(f'  {lang} translation: ERROR ({trans_response.status_code})')
    else:
        print(f'  Analysis endpoint failed: {response.status_code}')
