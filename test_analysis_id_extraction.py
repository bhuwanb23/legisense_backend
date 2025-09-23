#!/usr/bin/env python3
"""
Test script to verify analysis ID extraction works for all documents
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_analysis_id_extraction():
    """Test analysis ID extraction for all documents with analysis"""
    
    # Get all documents
    docs_response = requests.get(f"{BASE_URL}/api/documents/")
    if docs_response.status_code != 200:
        print(f"❌ Failed to fetch documents: {docs_response.status_code}")
        return
    
    documents = docs_response.json()
    print(f"📄 Found {len(documents)} documents")
    
    for doc in documents:
        doc_id = doc['id']
        print(f"\n🔍 Testing Document {doc_id}...")
        
        # Test analysis endpoint
        analysis_response = requests.get(f"{BASE_URL}/api/documents/{doc_id}/analysis/")
        
        if analysis_response.status_code == 404:
            print(f"   ⚠️  No analysis available for document {doc_id}")
            continue
        elif analysis_response.status_code != 200:
            print(f"   ❌ Analysis endpoint failed: {analysis_response.status_code}")
            continue
        
        analysis_data = analysis_response.json()
        analysis_id = analysis_data.get('id')
        has_analysis = 'analysis' in analysis_data
        
        print(f"   ✅ Analysis ID: {analysis_id}")
        print(f"   ✅ Has analysis data: {has_analysis}")
        
        if analysis_id and has_analysis:
            # Test translation for this analysis
            for lang in ['hi', 'ta', 'te']:
                print(f"   🌐 Testing {lang} translation...")
                
                # Try to get existing translation
                trans_response = requests.get(f"{BASE_URL}/api/analysis/{analysis_id}/translations/{lang}/")
                
                if trans_response.status_code == 200:
                    print(f"      ✅ {lang} translation exists")
                elif trans_response.status_code == 404:
                    # Try to create translation
                    create_response = requests.post(
                        f"{BASE_URL}/api/analysis/{analysis_id}/translate/",
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps({'language': lang})
                    )
                    
                    if create_response.status_code == 200:
                        print(f"      ✅ {lang} translation created successfully")
                    else:
                        print(f"      ❌ Failed to create {lang} translation: {create_response.status_code}")
                else:
                    print(f"      ❌ Translation check failed: {trans_response.status_code}")

if __name__ == "__main__":
    test_analysis_id_extraction()
