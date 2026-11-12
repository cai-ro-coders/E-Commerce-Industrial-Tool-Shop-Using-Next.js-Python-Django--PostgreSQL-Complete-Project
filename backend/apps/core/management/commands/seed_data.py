"""
Seed the Industrial Tool Shop with realistic demo data.

Usage:
    python manage.py seed_data            # idempotent seed
    python manage.py seed_data --reset    # delete demo data first

Demo accounts:
    admin@industrialtools.com    / Admin@12345
    staff@industrialtools.com    / Staff@12345
    customer@example.com         / Customer@12345
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

from apps.accounts.models import ActivityLog, Address, LoginHistory, User
from apps.brands.models import Brand
from apps.categories.models import Category
from apps.core.models import FileDocument, Setting
from apps.coupons.models import Coupon, CouponUsage
from apps.inventory.models import InventoryLog
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import Payment
from apps.products.models import Product, ProductImage, ProductSpecification
from apps.reviews.models import Review

fake = Faker()
Faker.seed(2026)
random.seed(2026)

CATEGORY_TREE = {
    "Power Tools": ["Drills & Drivers", "Saws & Cutting", "Grinders & Sanders"],
    "Hand Tools": ["Wrenches & Spanners", "Screwdrivers & Bits", "Pliers & Cutters", "Hammers & Striking"],
    "Measuring & Layout": ["Tape Measures", "Levels & Squares", "Laser Distance Meters"],
    "Safety Equipment": ["Eye & Face Protection", "Gloves", "Respiratory Protection"],
    "Fasteners": ["Bolts & Screws", "Anchors", "Nuts & Washers"],
    "Welding & Soldering": ["Welding Machines", "Welding Helmets", "Solder & Flux"],
    "Electrical": ["Testers & Meters", "Cable Management", "Switches & Outlets"],
    "Plumbing": ["Pipe Wrenches", "PEX & Fittings"],
    "Machining": ["Drill Bits", "End Mills", "Taps & Dies"],
    "Storage & Organization": ["Tool Boxes", "Tool Chests", "Shelving & Racks"],
    "Abrasives": ["Cut-Off Wheels", "Grinding Discs", "Sanding Belts"],
    "Air Tools": ["Air Compressors", "Impact Guns"],
    "Workwear": ["Safety Boots", "Work Jackets"],
}

BRANDS = [
    "DeWalt", "Makita", "Bosch", "Milwaukee", "Stanley", "Craftsman",
    "Black+Decker", "Ryobi", "Knipex", "Wera", "Wiha", "Fluke", "Klein Tools",
    "Ridgid", "Lincoln Electric", "Miller Electric", "3M", "Honeywell", "Irwin",
    "Lenox", "Diablo", "Freud", "Dremel", "Paslode", "Senco", "Metabo", "Hilti",
    "Festool", "Fein", "Greenlee", "Ideal", "Southwire", "Panduit",
    "Thomas & Betts", "Square D", "Eaton", "Siemens", "Schneider Electric",
    "Legrand", "Leviton", "Lutron", "Watts", "SharkBite", "Moen", "Delta",
    "Grainger", "Fastenal", "Simpson Strong-Tie", "Hillman", "Werner",
]

ITEMS = {
    "Power Tools": [
        ("20V MAX Cordless Drill Kit", 189), ("7-1/4 in Circular Saw", 229),
        ("4-1/2 in Angle Grinder", 149), ("Brushless Impact Driver", 199),
        ("Reciprocating Saw", 169), ("Random Orbit Sander", 129),
    ],
    "Hand Tools": [
        ("Combination Wrench Set", 89), ("Precision Screwdriver Set", 39),
        ("Diagonal Cutting Pliers", 34), ("16 oz Claw Hammer", 29),
        ("Adjustable Wrench", 24), ("Ratcheting Socket Set", 119),
    ],
    "Measuring & Layout": [
        ("25 ft Tape Measure", 24), ("48 in Spirit Level", 49),
        ("Laser Distance Meter 50m", 129), ("Digital Angle Finder", 59),
    ],
    "Safety Equipment": [
        ("Anti-Fog Safety Glasses", 18), ("Nitrile Grip Gloves", 15),
        ("Half-Mask Respirator", 69), ("Ear Protection Muffs", 27),
    ],
    "Fasteners": [
        ("Hex Bolt Assortment", 42), ("Concrete Anchor Kit", 55),
        ("Stainless Washer Pack", 19), ("Structural Screw 100-Pack", 64),
    ],
    "Welding & Soldering": [
        ("MIG Welder 180A", 749), ("Auto-Darkening Welding Helmet", 159),
        ("Rosin Core Solder Kit", 27), ("TIG Torch Assembly", 189),
    ],
    "Electrical": [
        ("True RMS Multimeter", 179), ("Cable Tie Assortment", 16),
        ("GFCI Outlet 20A", 24), ("Non-Contact Voltage Tester", 39),
    ],
    "Plumbing": [
        ("14 in Pipe Wrench", 59), ("PEX Crimp Tool Kit", 139),
        ("Copper Tube Cutter", 29),
    ],
    "Machining": [
        ("Cobalt Drill Bit Set", 89), ("Carbide End Mill 1/2 in", 69),
        ("HSS Tap & Die Set", 149), ("Annular Cutter Set", 219),
    ],
    "Storage & Organization": [
        ("24 in Tool Box", 49), ("Rolling Tool Chest", 399),
        ("Heavy-Duty Steel Shelving", 189), ("Stackable Organizer Set", 39),
    ],
    "Abrasives": [
        ("Cut-Off Wheel 10-Pack", 32), ("Flap Disc 4-1/2 in", 14),
        ("Sanding Belt Assortment", 28), ("Wire Cup Brush", 19),
    ],
    "Air Tools": [
        ("20 Gal Air Compressor", 529), ("1/2 in Impact Gun", 199),
        ("Air Blow Gun Kit", 24),
    ],
    "Workwear": [
        ("Steel-Toe Work Boots", 149), ("Insulated Work Jacket", 119),
        ("Hi-Vis Safety Vest", 29),
    ],
}

COMMENTS = [
    "Solid build quality. Held up through a full week on site.",
    "Exactly as described. Fast shipping and well packaged.",
    "Great value for the price. Will order more for the crew.",
    "The grip and balance are excellent for long shifts.",
    "Works well, though the case could be more rugged.",
    "Precise tolerances and no play. Very impressed.",
    "Replaced an older unit and this is a clear upgrade.",
    "Good tool, but the manual could be clearer.",
    "Our shop has standardized on this model. Reliable every time.",
    "Arrived on time and matched the spec sheet perfectly.",
    "Decent for light duty, not ideal for industrial use.",
    "The finish is excellent and it feels premium in hand.",
]

REVIEW_TITLES = [
    "Excellent quality", "Great value", "Solid performer", "Would buy again",
    "Good, with minor caveats", "Built to last", "Perfect for the workshop",
    "Reliable and accurate", "Impressive build", "Does the job well",
]

SETTINGS = [
    ("site_name", "general", "TorqueForge Industrial Supply"),
    ("site_tagline", "general", "Professional tools for serious work"),
    ("site_logo", "general", ""),
    ("site_description", "general", "Industrial tools, safety equipment, and supplies trusted by professionals."),
    ("support_email", "general", "support@torqueforge.test"),
    ("support_phone", "general", "+1 (800) 555-0139"),
    ("support_address", "general", "1842 Ironworks Avenue, Houston, TX 77002"),
    ("currency", "general", "USD"),
    ("currency_symbol", "general", "$"),
    ("tax_rate", "general", "8"),
    ("shipping_fee", "general", "15"),
    ("free_shipping_threshold", "general", "250"),
    ("company_name", "company", "TorqueForge Industrial Supply LLC"),
    ("company_tax_id", "company", "US-84-2910337"),
    ("company_registration", "company", "TX-2021-884219"),
    ("smtp_host", "smtp", "smtp.mailtrap.io"),
    ("smtp_port", "smtp", "587"),
    ("smtp_username", "smtp", "torqueforge-smtp"),
    ("smtp_encryption", "smtp", "tls"),
    ("smtp_from_email", "smtp", "orders@torqueforge.test"),
    ("stripe_publishable_key", "payment", ""),
    ("stripe_secret_key", "payment", ""),
    ("stripe_webhook_secret", "payment", ""),
    ("paypal_client_id", "payment", ""),
    ("paypal_client_secret", "payment", ""),
    ("paypal_mode", "payment", "sandbox"),
    ("language", "localization", "en"),
    ("timezone", "localization", "Asia/Manila"),
    ("date_format", "localization", "MM/DD/YYYY"),
    ("theme", "appearance", "light"),
    ("primary_color", "appearance", "#ea580c"),
    ("backup_frequency", "backup", "weekly"),
    ("items_per_page", "general", "10"),
]

FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]


def get_font(size):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]


def make_image(relative_path, title, subtitle, size=(800, 800), base=(30, 41, 59), accent=(234, 88, 12)):
    """Render a clean demo image and save it under MEDIA_ROOT."""
    from django.conf import settings

    path = settings.MEDIA_ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    img = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        color = tuple(int(base[i] + (accent[i] - base[i]) * ratio * 0.55) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    draw.rectangle([0, height - 12, width, height], fill=accent)
    draw.rounded_rectangle(
        [width * 0.08, height * 0.22, width * 0.92, height * 0.78],
        radius=28, outline=(255, 255, 255), width=3,
    )
    title_font = get_font(max(22, width // 14))
    subtitle_font = get_font(max(14, width // 30))
    lines = wrap_text(draw, title.upper(), title_font, width * 0.78)
    total = len(lines) * (title_font.size + 10)
    y = height / 2 - total / 2
    for line in lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((width - w) / 2, y), line, font=title_font, fill=(255, 255, 255))
        y += title_font.size + 10
    if subtitle:
        sub = subtitle.upper()[:48]
        w = draw.textlength(sub, font=subtitle_font)
        draw.text(((width - w) / 2, y + 14), sub, font=subtitle_font, fill=(255, 255, 255))
    img.save(path, "JPEG", quality=85, optimize=True)
    return relative_path


class Command(BaseCommand):
    help = "Seed 50 realistic records per major table for the Industrial Tool Shop."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete demo data before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Clearing existing data...")
            Review.objects.all().delete()
            Payment.objects.all().delete()
            OrderStatusHistory.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            CouponUsage.objects.all().delete()
            Coupon.objects.all().delete()
            InventoryLog.objects.all().delete()
            Notification.objects.all().delete()
            FileDocument.objects.all().delete()
            ProductSpecification.objects.all().delete()
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()
            Address.objects.all().delete()
            LoginHistory.objects.all().delete()
            ActivityLog.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            Setting.objects.all().delete()

        now = timezone.now()
        self.seed_settings()
        admin = self.seed_users()
        categories = self.seed_categories()
        brands = self.seed_brands()
        products = self.seed_products(categories, brands)
        customers = list(User.objects.filter(role="customer")[:50])
        addresses = self.seed_addresses(customers)
        coupons = self.seed_coupons()
        self.seed_orders(customers, addresses, products, coupons)
        self.seed_reviews(customers, products)
        self.seed_inventory(products, admin)
        self.seed_notifications(admin, customers)
        self.seed_activity(customers, admin)
        self.seed_files(admin)
        self.seed_wishlists(customers, products)

        self.stdout.write(self.style.SUCCESS("Seed complete:"))
        for label, model in [
            ("users", User), ("customers", User.objects.filter(role="customer")),
            ("categories", Category), ("brands", Brand), ("products", Product),
            ("product images", ProductImage), ("addresses", Address),
            ("orders", Order), ("order items", OrderItem), ("payments", Payment),
            ("coupons", Coupon), ("reviews", Review), ("inventory logs", InventoryLog),
            ("notifications", Notification), ("settings", Setting),
            ("login history", LoginHistory), ("activity logs", ActivityLog),
        ]:
            count = model.objects.count() if hasattr(model, "objects") else model.count()
            self.stdout.write(f"  {label:20s} {count}")
        self.stdout.write("")
        self.stdout.write("Admin login:    admin@industrialtools.com / Admin@12345")
        self.stdout.write("Staff login:    staff@industrialtools.com / Staff@12345")
        self.stdout.write("Customer login: customer@example.com / Customer@12345")

    # ------------------------------------------------------------------ users
    def seed_settings(self):
        for key, group, value in SETTINGS:
            Setting.objects.update_or_create(key=key, defaults={"group": group, "value": value})
        self.stdout.write("Settings ready.")

    def seed_users(self):
        def upsert(email, password, role, first, last, staff=False, superuser=False, phone=""):
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    "first_name": first, "last_name": last, "role": role,
                    "status": "active", "is_staff": staff, "is_superuser": superuser,
                    "phone": phone, "is_active": True,
                },
            )
            user.set_password(password)
            user.save()
            try:
                rel = f"avatars/{slugify(email)}.jpg"
                make_image(rel, first[0] + last[0], role, size=(300, 300), base=(15, 23, 42), accent=(234, 88, 12))
                user.avatar.name = rel
                user.save(update_fields=["avatar"])
            except Exception:
                pass
            return user

        admin = upsert("admin@industrialtools.com", "Admin@12345", "admin", "Marcus", "Reyes", True, True, "+1 800 555 0101")
        upsert("staff@industrialtools.com", "Staff@12345", "staff", "Dana", "Whitfield", True, False, "+1 800 555 0102")
        upsert("customer@example.com", "Customer@12345", "customer", "Jordan", "Blake", False, False, "+1 555 010 2200")

        for i in range(1, 50):
            first, last = fake.first_name(), fake.last_name()
            email = f"customer{i:02d}@example.com"
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    "first_name": first, "last_name": last, "role": "customer",
                    "status": "inactive" if i % 17 == 0 else "active",
                    "phone": fake.phone_number()[:40], "is_active": i % 17 != 0,
                },
            )
            user.set_password("Customer@12345")
            user.save()
        self.stdout.write(f"Users ready: {User.objects.count()}")
        return admin

    def seed_categories(self):
        created = []
        palette = [(15, 23, 42), (30, 41, 59), (51, 65, 85), (69, 26, 3), (20, 83, 45), (12, 74, 110)]
        for p_index, (parent_name, children) in enumerate(CATEGORY_TREE.items()):
            parent, _ = Category.objects.update_or_create(
                name=parent_name,
                defaults={
                    "parent": None,
                    "description": f"Professional-grade {parent_name.lower()} for industrial and commercial applications.",
                    "status": "active",
                },
            )
            rel = f"categories/{slugify(parent_name)}.jpg"
            make_image(rel, parent_name, "Industrial supply", size=(640, 420), base=palette[p_index % len(palette)])
            parent.image.name = rel
            parent.save(update_fields=["image", "slug"])
            created.append(parent)
            for child_name in children:
                child, _ = Category.objects.update_or_create(
                    name=child_name,
                    defaults={
                        "parent": parent,
                        "description": f"{child_name} sourced for trade professionals and maintenance teams.",
                        "status": "active",
                    },
                )
                rel = f"categories/{slugify(child_name)}.jpg"
                make_image(rel, child_name, parent_name, size=(640, 420), base=palette[(p_index + 2) % len(palette)], accent=(59, 130, 246))
                child.image.name = rel
                child.save(update_fields=["image", "slug"])
                created.append(child)
        self.stdout.write(f"Categories ready: {len(created)}")
        return created

    def seed_brands(self):
        brands = []
        palette = [(127, 29, 29), (20, 83, 45), (30, 58, 138), (88, 28, 135), (120, 53, 15), (15, 118, 110)]
        for i, name in enumerate(BRANDS):
            brand, _ = Brand.objects.update_or_create(
                name=name,
                defaults={"description": f"{name} professional tools and industrial equipment.", "status": "active"},
            )
            rel = f"brands/{slugify(name)}.jpg"
            make_image(rel, name, "Authorized brand", size=(320, 320), base=palette[i % len(palette)], accent=(255, 255, 255))
            brand.logo.name = rel
            brand.save(update_fields=["logo", "slug"])
            brands.append(brand)
        self.stdout.write(f"Brands ready: {len(brands)}")
        return brands

    def seed_products(self, categories, brands):
        leaves = [c for c in categories if c.parent_id]
        parent_by_id = {c.id: c for c in categories}
        existing = list(Product.objects.all())
        products = []
        for i in range(50):
            category = leaves[i % len(leaves)]
            parent = parent_by_id.get(category.parent_id, category)
            pool = ITEMS.get(parent.name, ITEMS["Hand Tools"])
            item_name, base_price = pool[i % len(pool)]
            brand = brands[i % len(brands)]
            name = f"{brand.name} {item_name}"
            sku = f"IT-{i + 1:04d}-{slugify(brand.name)[:3].upper()}"
            price = Decimal(str(round(base_price * random.uniform(0.92, 1.18), 2)))
            cost = (price * Decimal(str(random.uniform(0.52, 0.72)))).quantize(Decimal("0.01"))
            on_sale = i % 4 == 0
            sale_price = (price * Decimal(str(random.uniform(0.72, 0.88)))).quantize(Decimal("0.01")) if on_sale else None
            if i in (3, 11, 27, 41):
                stock = 0
            elif i in (5, 9, 18, 33, 44):
                stock = random.randint(1, 5)
            else:
                stock = random.randint(12, 240)
            status = "active" if i % 13 else "draft"
            if i in (19, 38):
                status = "inactive"
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "category": category,
                    "brand": brand,
                    "name": name,
                    "short_description": f"{name} — dependable performance for demanding industrial environments.",
                    "description": (
                        f"<p>The <strong>{name}</strong> is engineered for professional trades and industrial "
                        f"maintenance teams. Built with durable materials, precise tolerances, and a "
                        f"comfortable grip for extended use.</p>"
                        f"<ul><li>Industrial-grade construction</li><li>Backed by a limited 3-year warranty</li>"
                        f"<li>Tested to {random.choice(['ISO 9001', 'ANSI', 'CE', 'OSHA'])} standards</li></ul>"
                    ),
                    "price": price,
                    "sale_price": sale_price,
                    "cost_price": cost,
                    "weight": Decimal(str(round(random.uniform(0.4, 18), 2))),
                    "dimensions": f"{random.randint(10, 60)} x {random.randint(5, 40)} x {random.randint(3, 30)} cm",
                    "stock_quantity": stock,
                    "minimum_stock": random.choice([5, 8, 10, 12, 15]),
                    "featured": i % 5 == 0,
                    "status": status,
                },
            )
            make_image(
                f"products/{product.slug}-1.jpg", name, category.name,
                size=(800, 800), base=(15, 23, 42),
                accent=random.choice([(234, 88, 12), (37, 99, 235), (22, 163, 74), (147, 51, 234)]),
            )
            ProductImage.objects.filter(product=product).delete()
            image = ProductImage(product=product, is_primary=True, sort_order=0)
            image.image.name = f"products/{product.slug}-1.jpg"
            image.save()
            if i % 3 == 0:
                make_image(
                    f"products/{product.slug}-2.jpg", f"{item_name} detail", "In use",
                    size=(800, 800), base=(30, 41, 59), accent=(71, 85, 105),
                )
                second = ProductImage(product=product, is_primary=False, sort_order=1)
                second.image.name = f"products/{product.slug}-2.jpg"
                second.save()

            product.specifications.all().delete()
            specs = [
                ("Brand", brand.name),
                ("Model", f"{sku}-{random.randint(100, 999)}"),
                ("Voltage / Power", random.choice(["20V MAX", "120V AC", "18V", "Manual", "12V DC"])),
                ("Warranty", random.choice(["3 years", "2 years", "5 years", "1 year"])),
                ("Country of Origin", random.choice(["USA", "Germany", "Japan", "Taiwan", "Mexico"])),
                ("Package Contents", "Tool, manual, carrying case"),
            ]
            for attr, value in random.sample(specs, k=5):
                ProductSpecification.objects.create(product=product, attribute_name=attr, attribute_value=value)
            products.append(product)
        self.stdout.write(f"Products ready: {len(products)}")
        return products

    def seed_addresses(self, customers):
        cities = [
            ("Houston", "Texas", "77002"), ("Chicago", "Illinois", "60607"),
            ("Phoenix", "Arizona", "85004"), ("Atlanta", "Georgia", "30303"),
            ("Denver", "Colorado", "80202"), ("Seattle", "Washington", "98101"),
            ("Detroit", "Michigan", "48226"), ("Dallas", "Texas", "75201"),
        ]
        addresses = []
        for i, customer in enumerate(customers):
            city, province, postal = cities[i % len(cities)]
            address, _ = Address.objects.update_or_create(
                user=customer,
                address_line_1=f"{fake.building_number()} {fake.street_name()}",
                defaults={
                    "full_name": customer.full_name,
                    "phone": customer.phone or fake.phone_number()[:40],
                    "address_line_2": f"Suite {random.randint(100, 900)}",
                    "city": city, "province": province, "postal_code": postal,
                    "country": "United States", "is_default": True,
                },
            )
            addresses.append(address)
            if i % 3 == 0:
                second, _ = Address.objects.update_or_create(
                    user=customer,
                    address_line_1=f"{fake.building_number()} Industrial Park Dr",
                    defaults={
                        "full_name": f"{customer.full_name} (Warehouse)",
                        "phone": customer.phone or fake.phone_number()[:40],
                        "address_line_2": "Dock 4",
                        "city": city, "province": province, "postal_code": postal,
                        "country": "United States", "is_default": False,
                    },
                )
                addresses.append(second)
        self.stdout.write(f"Addresses ready: {len(addresses)}")
        return addresses

    def seed_coupons(self):
        coupons = []
        today = timezone.now()
        for i in range(50):
            is_percentage = i % 2 == 0
            code = f"{'SAVE' if is_percentage else 'FLAT'}{5 + (i * 3) % 40}" if i < 12 else f"TOOL{i + 1:02d}{random.choice(['A', 'B', 'X'])}"
            coupon, _ = Coupon.objects.update_or_create(
                code=code,
                defaults={
                    "type": "percentage" if is_percentage else "fixed",
                    "value": random.choice([5, 10, 15, 20, 25]) if is_percentage else random.choice([10, 25, 50, 75, 100]),
                    "minimum_order": random.choice([0, 50, 100, 150, 250]),
                    "maximum_discount": 150 if is_percentage else None,
                    "usage_limit": random.choice([0, 50, 100, 250]),
                    "used_count": random.randint(0, 20),
                    "start_date": today - timedelta(days=random.randint(1, 90)),
                    "end_date": today + timedelta(days=random.choice([-15, 30, 60, 120, 180])),
                    "status": "inactive" if i in (7, 23, 41) else "active",
                },
            )
            coupons.append(coupon)
        self.stdout.write(f"Coupons ready: {len(coupons)}")
        return coupons

    def seed_orders(self, customers, addresses, products, coupons):
        if Order.objects.exists():
            self.stdout.write("Orders already exist — skipping order seed.")
            return
        statuses = ["delivered"] * 18 + ["shipped"] * 8 + ["processing"] * 8 + ["pending"] * 8 + ["cancelled"] * 4 + ["returned"] * 4
        methods = ["cod", "card", "paypal", "stripe", "bank"]
        now = timezone.now()
        used_numbers = set()
        for i in range(50):
            customer = random.choice(customers)
            customer_addresses = [a for a in addresses if a.user_id == customer.id]
            address = random.choice(customer_addresses) if customer_addresses else addresses[0]
            days_ago = random.randint(0, 180)
            created = now - timedelta(days=days_ago, hours=random.randint(0, 20), minutes=random.randint(0, 59))
            status = statuses[i]
            if status in ("delivered", "shipped"):
                payment_status = "paid" if random.random() < 0.9 else "pending"
            elif status == "returned":
                payment_status = "refunded"
            elif status == "cancelled":
                payment_status = "refunded" if random.random() < 0.5 else "failed"
            else:
                payment_status = random.choice(["pending", "pending", "paid"])
            method = random.choice(methods)
            chosen = random.sample(products, k=random.randint(1, 4))
            subtotal = Decimal("0")
            line_data = []
            for product in chosen:
                qty = random.randint(1, 3)
                price = product.effective_price
                subtotal += price * qty
                line_data.append((product, qty, price))
            coupon = random.choice(coupons) if random.random() < 0.3 else None
            discount = coupon.calculate_discount(subtotal) if coupon else Decimal("0")
            shipping = Decimal("0") if subtotal >= 250 else Decimal("15")
            tax = ((subtotal - discount) * Decimal("0.08")).quantize(Decimal("0.01"))
            grand = subtotal - discount + shipping + tax
            number = f"ORD-{created.strftime('%Y%m%d')}-{i + 1:05d}"
            while number in used_numbers:
                number = f"ORD-{created.strftime('%Y%m%d')}-{i + 1:05d}{random.randint(0, 99)}"
            used_numbers.add(number)
            order = Order.objects.create(
                user=customer,
                order_number=number,
                subtotal=subtotal,
                discount=discount,
                shipping_fee=shipping,
                tax=tax,
                grand_total=grand,
                payment_method=method,
                payment_status=payment_status,
                order_status=status,
                shipping_address=address,
                coupon=coupon if discount else None,
                notes=random.choice(["", "Please call before delivery.", "Leave at loading dock.", "Handle with care."]),
                tracking_number=f"1Z{random.randint(10**9, 10**10 - 1)}" if status in ("shipped", "delivered", "returned") else "",
            )
            Order.objects.filter(pk=order.pk).update(created_at=created, updated_at=created)
            for product, qty, price in line_data:
                OrderItem.objects.create(
                    order=order, product=product, product_name=product.name,
                    sku=product.sku, quantity=qty, price=price,
                    cost_price=product.cost_price, total=price * qty,
                )
            Payment.objects.create(
                order=order,
                transaction_id=f"TXN-{number}",
                payment_gateway=method,
                amount=grand,
                currency="USD",
                status="paid" if payment_status == "paid" else ("refunded" if payment_status == "refunded" else "pending"),
                paid_at=created + timedelta(minutes=30) if payment_status == "paid" else None,
            )
            if coupon and discount:
                CouponUsage.objects.create(coupon=coupon, user=customer, order=order, discount_amount=discount)
            history = [("pending", "Order placed", created)]
            if status in ("processing", "shipped", "delivered", "returned"):
                history.append(("processing", "Payment confirmed, preparing shipment", created + timedelta(hours=4)))
            if status in ("shipped", "delivered", "returned"):
                history.append(("shipped", "Handed to carrier", created + timedelta(days=1)))
            if status in ("delivered", "returned"):
                history.append(("delivered", "Delivered to customer", created + timedelta(days=3)))
            if status == "cancelled":
                history.append(("cancelled", "Order cancelled by customer", created + timedelta(days=1)))
            if status == "returned":
                history.append(("returned", "Return received and restocked", created + timedelta(days=8)))
            for h_status, note, when in history:
                entry = OrderStatusHistory.objects.create(order=order, status=h_status, note=note)
                OrderStatusHistory.objects.filter(pk=entry.pk).update(created_at=when)
            updates = {}
            if status in ("shipped", "delivered", "returned"):
                updates["shipped_at"] = created + timedelta(days=1)
            if status in ("delivered", "returned"):
                updates["delivered_at"] = created + timedelta(days=3)
            if status == "cancelled":
                updates["cancelled_at"] = created + timedelta(days=1)
            if updates:
                Order.objects.filter(pk=order.pk).update(**updates)
        self.stdout.write("Orders ready: 50")

    def seed_reviews(self, customers, products):
        Review.objects.all().delete()
        statuses = ["approved"] * 40 + ["pending"] * 7 + ["rejected"] * 3
        combos = set()
        created = 0
        while created < 50:
            customer = random.choice(customers)
            product = random.choice(products)
            if (customer.id, product.id) in combos:
                continue
            combos.add((customer.id, product.id))
            rating = random.choices([5, 4, 3, 2, 1], weights=[45, 30, 14, 7, 4])[0]
            Review.objects.create(
                product=product, user=customer, rating=rating,
                title=random.choice(REVIEW_TITLES),
                comment=random.choice(COMMENTS), status=statuses[created],
            )
            created += 1
        self.stdout.write("Reviews ready: 50")

    def seed_inventory(self, products, admin):
        InventoryLog.objects.all().delete()
        types = ["stock_in"] * 20 + ["stock_out"] * 15 + ["adjustment"] * 8 + ["return"] * 7
        now = timezone.now()
        for i in range(50):
            product = products[i % len(products)]
            kind = types[i]
            quantity = random.randint(1, 120) if kind != "adjustment" else random.randint(0, 200)
            when = now - timedelta(days=random.randint(0, 90), hours=random.randint(0, 20))
            log = InventoryLog.objects.create(
                product=product, type=kind, quantity=quantity,
                reference=f"{'PO' if kind == 'stock_in' else 'REF'}-{random.randint(10000, 99999)}",
                remarks=random.choice([
                    "Supplier delivery", "Cycle count correction", "Customer return restock",
                    "Damaged units removed", "Purchase order received",
                ]),
                created_by=admin,
                scheduled_date=(when + timedelta(days=random.randint(1, 30))).date() if i % 4 == 0 else None,
            )
            InventoryLog.objects.filter(pk=log.pk).update(created_at=when)
        self.stdout.write("Inventory logs ready: 50")

    def seed_notifications(self, admin, customers):
        Notification.objects.all().delete()
        broadcasts = [
            ("Welcome to TorqueForge", "The new admin dashboard is live. Explore reports and inventory tools.", "info"),
            ("Weekly inventory review", "5 products are below their minimum stock level and need replenishment.", "stock"),
            ("New order received", "A new order requires payment verification.", "order"),
            ("System backup completed", "The nightly database backup completed successfully.", "success"),
            ("Pending review moderation", "7 customer reviews are awaiting moderation.", "warning"),
            ("Price list updated", "Supplier pricing has been refreshed for Q4.", "info"),
            ("Low stock alert", "Cordless drill kits are running low in the main warehouse.", "stock"),
            ("Payment gateway notice", "Stripe test keys are active in this environment.", "info"),
            ("Holiday schedule", "Warehouse will be closed for the upcoming public holiday.", "warning"),
            ("Security reminder", "Rotate admin passwords every 90 days.", "warning"),
        ]
        for title, message, kind in broadcasts:
            Notification.objects.create(user=None, title=title, message=message, type=kind)
        for i in range(40):
            customer = random.choice(customers)
            order = customer.orders.first()
            Notification.objects.create(
                user=customer,
                title=f"Order {order.order_number} update" if order else "Account update",
                message="Your order status has changed. Track it from your account.",
                type="order",
                link=f"/orders/{order.pk}" if order else "/orders",
                is_read=random.random() < 0.4,
            )
        self.stdout.write("Notifications ready: 50")

    def seed_activity(self, customers, admin):
        ActivityLog.objects.all().delete()
        actions = [
            ("product.updated", "Updated product pricing"), ("order.status_changed", "Marked order as shipped"),
            ("customer.updated", "Updated customer record"), ("coupon.created", "Created percentage coupon"),
            ("auth.login", "User signed in"), ("inventory.adjusted", "Adjusted stock level"),
            ("review.moderated", "Approved a review"), ("setting.updated", "Updated store settings"),
        ]
        admin_user = User.objects.filter(role="admin").first()
        staff_user = User.objects.filter(role="staff").first()
        now = timezone.now()
        for i in range(50):
            action, desc = actions[i % len(actions)]
            log = ActivityLog.objects.create(
                user=admin_user if i % 2 == 0 else staff_user,
                action=action, description=desc, entity_type=action.split(".")[0],
                entity_id=str(random.randint(1, 60)),
                ip_address=f"192.168.1.{random.randint(2, 240)}",
            )
            ActivityLog.objects.filter(pk=log.pk).update(created_at=now - timedelta(days=random.randint(0, 60)))
        LoginHistory.objects.all().delete()
        for i in range(50):
            customer = random.choice(customers)
            success = random.random() > 0.15
            LoginHistory.objects.create(
                user=customer, email=customer.email,
                ip_address=f"10.0.0.{random.randint(2, 250)}",
                user_agent=random.choice([
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123",
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15",
                ]),
                success=success,
            )
        self.stdout.write("Activity + login history ready: 50 each")

    def seed_files(self, admin):
        FileDocument.objects.all().delete()
        samples = [
            ("Supplier Agreement 2026.pdf", "contract", "Master supply agreement with the primary fastener vendor."),
            ("Invoice INV-2026-0114.pdf", "invoice", "Invoice for the Q3 safety equipment purchase."),
            ("Warehouse Safety Checklist.pdf", "document", "Monthly OSHA inspection checklist."),
            ("Product Catalog Brochure.jpg", "image", "Print-ready catalog cover artwork."),
            ("Customer Account Notes.txt", "customer", "Notes from the industrial accounts review."),
            ("Warranty Terms.pdf", "document", "Standard limited warranty terms for power tools."),
            ("Customs Documentation.txt", "document", "Import documentation for the latest container."),
            ("Price List Q4.pdf", "document", "Distributor price list effective Q4."),
        ]
        for name, category, description in samples:
            content = (
                f"{name}\n\n{description}\n\n"
                "This is a sample document generated for the Industrial Tool Shop demo. "
                "Upload real contracts, invoices, and customer files through the file manager."
            )
            doc = FileDocument(
                name=name, category=category, description=description,
                uploaded_by=admin, size=len(content.encode()), content_type="text/plain",
            )
            doc.file.save(name.replace(" ", "_").rsplit(".", 1)[0] + ".txt", ContentFile(content.encode()), save=True)
        self.stdout.write("Files ready: 8")

    def seed_wishlists(self, customers, products):
        from apps.cart.models import Wishlist

        Wishlist.objects.all().delete()
        for customer in customers:
            for product in random.sample(products, k=random.randint(0, 3)):
                Wishlist.objects.get_or_create(user=customer, product=product)
        self.stdout.write("Wishlists ready.")
