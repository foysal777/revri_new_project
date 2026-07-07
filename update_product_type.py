import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')
django.setup()

from admin_dashboard.models import Product

def run():
    print("Updating Product models...")
    count = 0
    # Update all products that have 'ecommerce'
    products = Product.objects.filter(product_type='ecommerce')
    for p in products:
        p.product_type = 'assessment'
        p.save()
        count += 1
    print(f"Updated {count} products in the database.")

    print("Updating vector-store.json...")
    vector_file = 'data/vector-store.json'
    if os.path.exists(vector_file):
        with open(vector_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        updated_vector = 0
        for item in data.get('chunks', []):
            if item.get('product_type') == 'ecommerce':
                item['product_type'] = 'assessment'
                
                # Also replace in the content string
                if 'content' in item:
                    item['content'] = item['content'].replace('ecommerce', 'assessment').replace('Ecommerce', 'Assessment')
                
                updated_vector += 1
                
        with open(vector_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        print(f"Updated {updated_vector} entries in vector-store.json.")
    else:
        print(f"File {vector_file} not found.")

if __name__ == "__main__":
    run()
