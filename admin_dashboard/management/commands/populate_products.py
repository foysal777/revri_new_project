"""
Management command to populate the database with all BMC products/services
from the catalog spreadsheet and sync them into the AI vector store.

Usage:
    python manage.py populate_products
    python manage.py populate_products --force-reindex   # re-embeds all existing products too
"""
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile


BMC_CATALOG = [
    # ── 28 Assessments ($119 each, type=resource) ──
    {
        "name": "Assimilation Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Focuses on seamlessly integrating members into the church. "
            "Evaluates how well new attendees are welcomed, connected, and retained. "
            "Target Audience: Churches seeking to improve how new members are integrated "
            "into the congregation."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Bible Literacy Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates the congregation's understanding and familiarity with Scripture. "
            "Identifies knowledge gaps and informs educational programming. "
            "Target Audience: Churches evaluating their congregation's biblical knowledge "
            "and education needs."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Children's Ministry Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Focuses on evaluating and enhancing the children's ministry programs. "
            "Gathers parent and leader feedback on programming quality and spiritual growth. "
            "Target Audience: Churches evaluating the quality and effectiveness of their "
            "children's ministry program."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Christian Education Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates the effectiveness of the church's educational programs including "
            "Bible studies, Sunday school, and discipleship groups. "
            "Target Audience: Churches evaluating the effectiveness of Christian education "
            "and discipleship programming."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Church Outreach Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers members' perspectives on the effectiveness of outreach programs and "
            "community engagement. Identifies strengths and areas for improvement. "
            "Target Audience: Churches wanting to evaluate and improve community outreach "
            "programs and activities."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Church Technology Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers members' perceptions, concerns, and ideas regarding technology use "
            "within the church. Covers worship services, communication, outreach, and "
            "operations. Informs decisions on technology purchase, training, and "
            "implementation while maintaining spiritual focus. "
            "Target Audience: Churches evaluating their technology use across worship, "
            "communication, education, and operations."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Community Needs Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Seeks to understand the effectiveness of the church's community efforts, "
            "assessing outreach initiatives such as food pantries, job training, and "
            "addiction counseling. Helps leadership identify improvement areas and new "
            "ways to serve the marginalized. "
            "Target Audience: Churches seeking to better serve the practical needs of "
            "their surrounding community."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Crisis Response and Support Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates the church's role in providing comfort, care, and support in "
            "crises such as illness, grief, job loss, disasters, and trauma. Identifies "
            "areas for improvement in crisis response programs. "
            "Target Audience: Churches evaluating how well they support members through "
            "illness, grief, job loss, and other crises."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Culture Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Assesses how members perceive church culture including welcome, hospitality, "
            "diversity, inclusion, openness, trust, and moral values. Designed to align "
            "culture with the church's mission. "
            "Target Audience: Churches wanting to understand the unwritten norms, values, "
            "and attitudes that shape their community."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Digital Discipleship Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Captures members' perspectives on digital discipleship including online "
            "small groups, prayer support, and online ministry. Informs decisions "
            "regarding digital resources and training. "
            "Target Audience: Churches leveraging digital tools for spiritual growth, "
            "discipleship, and online ministry."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Engagement and Participation Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates the church's effectiveness in fostering active involvement across "
            "different life stages. Identifies barriers and opportunities to enhance "
            "service, community, and spiritual growth. "
            "Target Audience: Churches measuring how actively members are involved across "
            "all life stages and ministries."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Evangelism Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers members' perspectives on the church's outreach and evangelism "
            "efforts including training, events, and opportunities to share the Gospel. "
            "Target Audience: Churches evaluating how well they equip and mobilize "
            "members for outreach and witnessing."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Fruitfulness and Sustainability Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates the church's pursuit of impactful and enduring ministry. Focuses "
            "on spiritual fruit production and the viability of structures, resources, "
            "and leadership for future endeavors. "
            "Target Audience: Churches evaluating the long-term viability and spiritual "
            "impact of their ministry."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Generosity and Stewardship Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Assesses members' views on how effectively the church teaches financial "
            "giving, serving, and using individual talents. Evaluates preaching, "
            "discipleship, and volunteer mobilization. "
            "Target Audience: Churches evaluating how well they cultivate a culture of "
            "biblical giving and financial stewardship."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Human Flourishing Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates members' holistic growth and well-being — spiritual, physical, "
            "mental, and emotional. Identifies areas for improvement to create an "
            "environment where people can flourish in alignment with the abundant life "
            "promised by Jesus. "
            "Target Audience: Churches committed to holistic well-being of members."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Hybrid Ministry Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Addresses the church's transition to online and hybrid ministry models. "
            "Evaluates perspectives on sermon streaming, online small groups, remote "
            "fellowship events, and AV quality. "
            "Target Audience: Churches operating both in-person and online models seeking "
            "to evaluate their hybrid approach."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Impact and Transformation Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates the effectiveness of church ministries in facilitating personal "
            "growth in faith, character, and wholeness. Measures whether members are "
            "experiencing positive changes aligned with biblical principles. "
            "Target Audience: Churches evaluating whether their ministries are producing "
            "genuine life change and spiritual growth."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Leadership Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers self-assessment and feedback from pastors, staff, and ministry "
            "leaders to strengthen leadership development. Details strengths, growth "
            "areas, challenges, and successes. "
            "Target Audience: Churches evaluating pastoral, staff, and ministry "
            "leadership effectiveness."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Life Stage Needs Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers insights into the specific needs and challenges faced by different "
            "groups of members at different stages of life, from youth to seniors. "
            "Target Audience: Churches seeking to tailor ministry and support services "
            "to members at different life stages."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Life Transitions Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Focuses on the church's commitment to supporting members through life "
            "changes: graduation, marriage, illness, or loss. Gauges effectiveness of "
            "support groups, mentorship, and spiritual nurture. "
            "Target Audience: Churches supporting members through major life changes."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Pastoral Care Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Evaluates effectiveness of pastoral care in nurturing spiritual life, "
            "providing counsel, crisis support, visitation of ill/homebound members, "
            "and prayer engagement. "
            "Target Audience: Churches evaluating the quality and reach of their "
            "pastoral support and member care."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Relevance and Contextualization Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Assesses how well church ministries and messages engage with contemporary "
            "culture. Seeks feedback on worship services, sermons, programs, and "
            "community life addressing daily realities. "
            "Target Audience: Churches evaluating how well their messages and ministries "
            "connect with contemporary culture."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Spiritual Formation Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Assesses how well church programs support members' individual spiritual "
            "growth and discipleship journey. Gathers input to identify strengths and "
            "areas for improvement. "
            "Target Audience: Churches evaluating how effectively their programs support "
            "members' individual spiritual growth."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Staff Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers perspectives on staff performance, communication, trust, and morale. "
            "Shapes decisions on team structure, professional development, and goals. "
            "Target Audience: Church leadership evaluating internal team performance, "
            "morale, and organizational health."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Visitor Experience Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Seeks feedback from first-time guests on initial impressions, parking, "
            "welcome received, and overall environment. Helps churches understand how "
            "to serve visitors better and increase retention. "
            "Target Audience: Churches wanting to improve the first-time guest experience "
            "and increase retention."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Worship Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers congregation perspectives on worship services, assessing whether "
            "worship engages the mind, heart, and spirit to glorify God and change lives. "
            "Target Audience: Churches evaluating how effectively their worship services "
            "engage and transform the congregation."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Young Adult Ministry Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Gathers insights from young adults (millennials, Gen Z) on the effectiveness "
            "of ministries targeting their demographic, including Bible studies, worship, "
            "leadership development, and mentorship. "
            "Target Audience: Churches evaluating how effectively they engage, nurture, "
            "and develop young adults."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Youth Ministry Assessment",
        "product_type": "resource",
        "price": "119.00",
        "description": (
            "Dedicated to understanding the meaningfulness and impact of youth "
            "environments within the church. Evaluates programming, leadership, and "
            "spiritual growth opportunities for young members. "
            "Target Audience: Churches evaluating their youth programming and how "
            "meaningfully it engages young members."
        ),
        "link": "https://blackmillennialcafe.com",
    },

    # ── 9 Resources (books, downloads, reports) ──
    {
        "name": "Proven: The Unmeasured Power of the Black Church",
        "product_type": "resource",
        "price": "0.00",
        "description": (
            "A data-driven study of the Black church's social impact in local communities, "
            "providing empirical evidence for the often-unmeasured contribution of Black "
            "churches. Free download. "
            "Target Audience: Researchers, church leaders, nonprofits, and community "
            "organizations studying the Black church's community impact."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "I Still Believe in the Black Church (State of the Black Church Study)",
        "product_type": "resource",
        "price": "30.99",
        "description": (
            "Authored by BMC's founder, using data to decode the pain and promise of "
            "Black churches, particularly focusing on the perspectives of women and "
            "young adults. Book purchase. "
            "Target Audience: Pastors, church leaders, denominational leaders, and "
            "scholars seeking a data-informed understanding of today's Black church."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Black Millennials & Faith: A Profile",
        "product_type": "resource",
        "price": "29.99",
        "description": (
            "A comprehensive research profile of Black millennials' engagement with "
            "faith and church, offering data-driven insights into their beliefs, "
            "practices, and needs. "
            "Target Audience: Church leaders, ministry planners, and anyone seeking "
            "to engage Black millennials in faith contexts."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "What Google Can't Give (Book)",
        "product_type": "resource",
        "price": "15.99",
        "description": (
            "The debut book by BMC's founder, offering a groundbreaking look at the "
            "intersection of faith, technology, and culture. Proposes a new model for "
            "ministry that goes beyond search engines. "
            "Target Audience: Church leaders, pastors, and ministry developers seeking "
            "to better engage Black millennials."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "I Still Believe in the Black Church Companion Presentation",
        "product_type": "resource",
        "price": "15.99",
        "description": (
            "A companion presentation with ready-to-use slides, charts, data points, "
            "and discussion prompts from the State of the Black Church study. Digital "
            "download for leaders. "
            "Target Audience: Pastors, church leaders, and educators who want to "
            "present State of the Black Church study findings."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Trends in the Black Church — Digital Download (State of the Black Church Study)",
        "product_type": "resource",
        "price": "29.00",
        "description": (
            "Created in partnership with Barna Group, providing a robust data-driven "
            "overview of the Black church landscape. Digital download. "
            "Target Audience: Church leaders and organizations seeking a comprehensive "
            "overview of the Black church landscape."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Trends in the Black Church — Paperback (State of the Black Church Study)",
        "product_type": "resource",
        "price": "39.00",
        "description": (
            "The printed copy of the landmark State of the Black Church study report, "
            "created in partnership with Barna Group. Physical book. "
            "Target Audience: Church leaders, scholars, and organizations who prefer "
            "a physical copy of the research report."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Open Table Bible Study Curriculum",
        "product_type": "resource",
        "price": "150.00",
        "description": (
            "A comprehensive Bible study curriculum introducing opportunities for "
            "engagement and discipleship. Includes multiple sessions and leader guides. "
            "Target Audience: Small groups, Sunday school classes, and church-wide "
            "Bible study programs."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Re-Entry Survey Template",
        "product_type": "resource",
        "price": "0.00",
        "description": (
            "A standardized free survey template for planning congregational re-entry "
            "after closures or transitions. Ready-to-use digital download. "
            "Target Audience: Churches planning post-pandemic or post-closure "
            "re-entry strategies."
        ),
        "link": "https://blackmillennialcafe.com",
    },

    # ── 3 Services & Programs (type=consultancy) ──
    {
        "name": "BMC Monthly Webinar Series",
        "product_type": "consultancy",
        "price": None,
        "description": (
            "Monthly live 90-minute webinars hosted by the BMC CEO and Barna State of "
            "the Black Church co-author. Delivers exclusive data insights on contemporary "
            "ministry topics. Subscription-based access. "
            "Target Audience: Pastors, church staff, ministry leaders, and clergy of "
            "Black churches seeking data-driven professional development."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "Black Church Leader — Monthly Subscription",
        "product_type": "consultancy",
        "price": None,
        "description": (
            "A monthly training and coaching membership platform for Black church "
            "leaders. Includes exclusive Masterclasses with Dr. Brianna K. Parker, "
            "automated certificates, and training covering Digital Discipleship, "
            "Next Gen, and Volunteerism. "
            "Target Audience: Pastors, clergy, ministry leaders, and staff ministers "
            "wanting consistent team-wide professional development."
        ),
        "link": "https://blackmillennialcafe.com",
    },
    {
        "name": "CEBA Journey™ — Discipleship Framework",
        "product_type": "consultancy",
        "price": None,
        "description": (
            "A culturally-informed, research-backed discipleship framework developed "
            "specifically by Black Millennial Cafe for Black churches and communities "
            "of color. The CEBA Journey guides individuals through four developmental "
            "stages: Curious, Connected, Builder, and Multiplier. "
            "Target Audience: Black churches and communities of color seeking a "
            "culturally-informed discipleship framework for all stages of faith."
        ),
        "link": "https://blackmillennialcafe.com",
    },
]


class Command(BaseCommand):
    help = "Populate the database with all BMC catalog products and sync them to the AI vector store."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-reindex",
            action="store_true",
            help="Force re-embedding of existing products too.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without saving.",
        )

    def handle(self, *args, **options):
        from admin_dashboard.models import Product
        from chatsystem.ai import vector_store, embed_text, _index_product_instance, sync_all_products

        dry_run = options["dry_run"]
        force_reindex = options["force_reindex"]

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== BMC Product Population ==="))
        self.stdout.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE'} | Force reindex: {force_reindex}\n")

        existing_names = set(Product.objects.values_list("name", flat=True))
        self.stdout.write(f"Products currently in DB: {len(existing_names)}\n")

        created, skipped, errors = 0, 0, []

        for item in BMC_CATALOG:
            name = item["name"]

            if name in existing_names:
                skipped += 1
                self.stdout.write(f"  [SKIP] {name}")
                if force_reindex:
                    try:
                        p = Product.objects.get(name=name)
                        if not dry_run:
                            _index_product_instance(p)
                        self.stdout.write(f"         └─ re-indexed ✓")
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"         └─ reindex error: {e}"))
                continue

            self.stdout.write(f"  [ADD]  {name}")
            if dry_run:
                created += 1
                continue

            try:
                product = Product(
                    name=name,
                    product_type=item["product_type"],
                    link=item.get("link") or "https://blackmillennialcafe.com",
                    description=item.get("description") or "",
                    product_price=item.get("price"),
                    is_published=True,
                )
                product.save()
                # Save a placeholder image so product_image field isn't empty
                product.product_image.save(
                    "bmc_default.jpg",
                    ContentFile(b"\xff\xd8\xff\xe0" + b"\x00" * 100),  # minimal JPEG header
                    save=True,
                )
                created += 1
                self.stdout.write(f"         └─ saved (id={product.id}) ✓")
            except Exception as e:
                errors.append(f"{name}: {e}")
                self.stdout.write(self.style.ERROR(f"         └─ ERROR: {e}"))

        # Summary
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"✓ Created: {created}"))
        self.stdout.write(f"  Skipped (existing): {skipped}")
        if errors:
            self.stdout.write(self.style.ERROR(f"✗ Errors: {len(errors)}"))
            for err in errors:
                self.stdout.write(self.style.ERROR(f"  - {err}"))

        # Now sync ALL products into vector store
        if not dry_run:
            self.stdout.write("\n" + self.style.MIGRATE_HEADING("=== Syncing vector store ==="))
            result = sync_all_products()
            self.stdout.write(self.style.SUCCESS(
                f"✓ Vector store synced: {result['synced']}/{result['total']} products indexed"
            ))
        else:
            self.stdout.write("\n[DRY RUN] Skipping vector store sync.")

        self.stdout.write(self.style.SUCCESS("\nDone!\n"))
