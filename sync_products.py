import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')
django.setup()

from admin_dashboard.models import Product

DATA = {
  "Assessments": [
    {"name": "Assimilation Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/assimilation-assessment"},
    {"name": "Bible Literacy Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/bible-literacy"},
    {"name": "Children's Ministry Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/childrens-ministry-assessment"},
    {"name": "Christian Education Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/christian-education-assessment"},
    {"name": "Church Outreach Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/church-outreach-assessment"},
    {"name": "Church Technology Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/church-technology-assessment"},
    {"name": "Community Needs Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/community-needs-assessment"},
    {"name": "Crisis Response and Support Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/crisis-response-and-support-assessment"},
    {"name": "Culture Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/culture-assessment"},
    {"name": "Digital Discipleship Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/digital-discipleship-assessment"},
    {"name": "Engagement and Participation Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/engagement-and-participation-assessment"},
    {"name": "Evangelism Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/evangelism-assessment"},
    {"name": "Fruitfulness and Sustainability Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/fruitfulness-and-sustainability-assessment"},
    {"name": "Generosity and Stewardship Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/generosity-and-stewardship-assessment"},
    {"name": "Human Flourishing Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/human-flourishing-assessment"},
    {"name": "Hybrid Ministry Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/hybrid-ministry-assessment-1"},
    {"name": "Impact and Transformation Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/hybrid-ministry-assessment"},
    {"name": "Leadership Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/leadership-assessment"},
    {"name": "Life Stage Needs Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/life-stage-needs-assessment"},
    {"name": "Life Transitions Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/life-transitions-assessment"},
    {"name": "Pastoral Care Assessment", "link": "https://shop.irunbmc.com/products/pastoral-care-assessment"},
    {"name": "Relevance and Contextualization Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/relevance-and-contextualization-assessment-1"},
    {"name": "Spiritual Formation Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/relevance-and-contextualization-assessment"},
    {"name": "Staff Assessment", "link": "https://shop.irunbmc.com/products/staff-assessment"},
    {"name": "Visitor Experience Assessment", "link": "https://shop.irunbmc.com/products/visitor-experience-assessment"},
    {"name": "Worship Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/worship-assessment"},
    {"name": "Young Adult Ministry Assessment", "link": "https://shop.irunbmc.com/collections/assessments/products/young-adult-ministry-assessment"},
    {"name": "Youth Ministry Assessment", "link": "https://shop.irunbmc.com/products/youth-ministry-assessment"}
  ],
  "Resources": [
    {"name": "Proven: The Unmeasured Power of the Black Church — A Data-Driven Study of Its Social Impact in Local Communities", "link": "https://shop.irunbmc.com/collections/resources/products/proven-the-unmeasured-power-of-the-black-church-a-data-driven-study-of-its-social-impact-in-local-communities"},
    {"name": "I Still Believe in the Black Church: Using Data to Decode the Pain and Promise of the Black Church (from the State of the Black Church Study)", "link": "https://shop.irunbmc.com/collections/resources/products/i-still-believe-in-the-black-church-from-the-state-of-the-black-church-study"},
    {"name": "Black Millennials & Faith: A Profile", "link": "https://shop.irunbmc.com/collections/resources/products/black-millennials-faith-a-profile"},
    {"name": "What Google Can't Give (Book)", "link": "https://shop.irunbmc.com/collections/resources/products/what-google-cant-give"},
    {"name": "I Still Believe in the Black Church Companion Presentation", "link": "https://shop.irunbmc.com/collections/resources/products/i-still-believe-in-the-black-church-companion-presentation"},
    {"name": "Trends in the Black Church — Digital Download (State of the Black Church Study)", "link": "https://shop.irunbmc.com/products/trends-in-the-black-church-from-the-state-of-the-black-church-study"},
    {"name": "Trends in the Black Church — Paperback (State of the Black Church Study)", "link": "https://shop.irunbmc.com/products/trends-in-the-black-church-from-the-state-of-the-black-church-study"},
    {"name": "Open Table Bible Study Curriculum", "link": "https://shop.irunbmc.com/products/open-table-bible-study-curriculum"},
    {"name": "Re-Entry Survey Template", "link": "https://shop.irunbmc.com/"}
  ],
  "Services & Programs": [
    {"name": "BMC Monthly Webinar Series", "link": "https://www.irunbmc.com/webinars"},
    {"name": "Black Church Leader — Monthly Subscription", "link": "https://www.blackchurchleader.com/"},
    {"name": "CEBA Journey™ — Discipleship Framework", "link": "https://www.irunbmc.com/CEBA"}
  ]
}

def run():
    print("Updating product links from extracted data...")
    updated_count = 0
    not_found = []

    for category, products in DATA.items():
        for item in products:
            name = item["name"].strip()
            link = item["link"].strip()

            # Update the product in the database by name (case-insensitive exact match)
            db_products = Product.objects.filter(name__iexact=name)
            if db_products.exists():
                for p in db_products:
                    p.link = link
                    p.save()
                    updated_count += 1
                    print(f"Updated: {p.name}")
            else:
                # Fallback to partial match if exact match fails
                db_products_partial = Product.objects.filter(name__icontains=name[:20]) # Match start of name
                if db_products_partial.exists():
                    for p in db_products_partial:
                        p.link = link
                        p.save()
                        updated_count += 1
                        print(f"Updated (Partial Match): '{p.name}' matched with '{name}'")
                else:
                    not_found.append(name)

    print(f"\nSuccessfully updated {updated_count} products.")
    if not_found:
        print(f"Could not find matching products in DB for the following ({len(not_found)}):")
        for nf in not_found:
            print(f" - {nf}")

if __name__ == "__main__":
    run()
