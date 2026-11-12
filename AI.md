AI 

E-Commerce Industrial Tool Shop Using Next.js Python Django REST Framework

Build a Complete Admin E-Commerce Industrial Tool Shop 
Frontend
-Next.js (App Router)
-React
-TypeScript
-Tailwind CSS v4
-TanStack Query for API data fetching and caching.
-Chart.js
-FullCalendar
-DataTables
-SweetAlert2
-React Hook Form
-Zod
-Lucide React Icons
-TailwindCSS
Backend
-Python Django
-Django REST Framework
-Django Simple JWT
-django-filter
-Django CORS Headers
-Pillow
-Python virtualenv
Database
-PostgreSQL
-Django ORM
-Django migrations

postgres database : 
database name : ecommerce
username : postgresdb
password : cairocoders
host : localhost
port : 5432

E-Commerce Industrial Tool Shop Database Schema

users
    `role` enum('admin','customer', 'staff') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'customer',

categories
    id (PK)
    parent_id (FK → categories.id, nullable)
    name
    slug
    image
    description
    status
    created_at
    updated_at
brands
    id (PK)
    name
    slug
    logo
    description
    status
    created_at
    updated_at
products
    id (PK)
    category_id (FK → categories.id)
    brand_id (FK → brands.id)
    sku (unique)
    name
    slug
    short_description
    description
    price
    sale_price
    cost_price
    weight
    dimensions
    stock_quantity
    minimum_stock
    featured
    status
    created_at
    updated_at
product_images
    id (PK)
    product_id (FK → products.id)
    image
    is_primary
    sort_order
    created_at
    updated_at
product_specifications
    id (PK)
    product_id (FK → products.id)
    attribute_name
    attribute_value
    created_at
    updated_at
addresses
    id (PK)
    user_id (FK → users.id)
    full_name
    phone
    address_line_1
    address_line_2
    city
    province
    postal_code
    country
    is_default
    created_at
    updated_at
carts
    id (PK)
    user_id (FK → users.id)
    created_at
    updated_at
cart_items
    id (PK)
    cart_id (FK → carts.id)
    product_id (FK → products.id)
    quantity
    price
    created_at
    updated_at
wishlists
    id (PK)
    user_id (FK → users.id)
    product_id (FK → products.id)
    created_at
    updated_at
orders
    id (PK)
    user_id (FK → users.id)
    order_number
    subtotal
    discount
    shipping_fee
    tax
    grand_total
    payment_method
    payment_status
    order_status
    shipping_address_id (FK → addresses.id)
    notes
    created_at
    updated_at
Order Status
    Pending
    Processing
    Shipped
    Delivered
    Cancelled
    Returned
Payment Status
    Pending
    Paid
    Failed
    Refunded
order_items
    id (PK)
    order_id (FK → orders.id)
    product_id (FK → products.id)
    product_name
    sku
    quantity
    price
    total
    created_at
    updated_at
payments
    id (PK)
    order_id (FK → orders.id)
    transaction_id
    payment_gateway
    amount
    currency
    status
    paid_at
    created_at
    updated_at
reviews
    id (PK)
    product_id (FK → products.id)
    user_id (FK → users.id)
    rating
    title
    comment
    status
    created_at
    updated_at
coupons
    id (PK)
    code
    type
    value
    minimum_order
    maximum_discount
    usage_limit
    used_count
    start_date
    end_date
    status
    created_at
    updated_at
Coupon Types
    percentage
    fixed
coupon_usages
    id (PK)
    coupon_id (FK → coupons.id)
    user_id (FK → users.id)
    order_id (FK → orders.id)
    discount_amount
    created_at
    updated_at
inventory_logs
    id (PK)
    product_id (FK → products.id)
    type
    quantity
    reference
    remarks
    created_at
    updated_at
Inventory Types
    stock_in
    stock_out
    adjustment
    return
settings
    id (PK)
    key
    value
    created_at
    updated_at
Common Settings
    site_name
    site_logo
    support_email
    support_phone
    currency
    tax_rate
    shipping_fee
settings
    id (PK)
    key
    group
    value
    created_at
    updated_at
data
    1
        key: stripe_publishable_key
        group: payment
        value: pk_test
    2
        key: stripe_secret_key
        group: payment
        value: sk_test
    3
        key: paypal_client_id
        group: payment
        value: test
    4
        key: paypal_client_secret
        group: payment
        value: test
site_name
site_logo
support_email
support_phone
currency
tax_rate
shipping_fee

Relationships Overview
Category
 └── hasMany Products

Brand
 └── hasMany Products

Product
 ├── belongsTo Category
 ├── belongsTo Brand
 ├── hasMany ProductImages
 ├── hasMany ProductSpecifications
 ├── hasMany Reviews
 └── hasMany OrderItems

User
 ├── hasMany Addresses
 ├── hasMany Orders
 ├── hasMany Reviews
 ├── hasMany Wishlist
 └── hasOne Cart

Order
 ├── belongsTo User
 ├── hasMany OrderItems
 ├── hasOne Payment
 └── belongsTo Address

Theme:

Modern
Professional
Mobile Friendly

Generate Realistic Data 50 records
===========================================
PROJECT STRUCTURE
ecommerce_industrial_tool/
│
├── frontend/
│   ├── app/
│   │   ├── (storefront)/
│   │   │   ├── page.tsx
│   │   │   ├── products/
│   │   │   ├── categories/
│   │   │   ├── brands/
│   │   │   ├── cart/
│   │   │   ├── checkout/
│   │   │   ├── orders/
│   │   │   ├── account/
│   │   │   └── contact/
│   │   │
│   │   ├── admin/
│   │   │   ├── login/
│   │   │   ├── dashboard/
│   │   │   ├── products/
│   │   │   ├── orders/
│   │   │   ├── customers/
│   │   │   ├── categories/
│   │   │   ├── brands/
│   │   │   ├── coupons/
│   │   │   ├── reviews/
│   │   │   ├── users/
│   │   │   ├── settings/
│   │   │   ├── notifications/
│   │   │   ├── files/
│   │   │   └── reports/
│   │   │
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   └── providers.tsx
│   │
│   ├── components/
│   │   ├── ui/
│   │   ├── storefront/
│   │   ├── admin/
│   │   ├── forms/
│   │   ├── tables/
│   │   └── charts/
│   │
│   ├── hooks/
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   ├── utils.ts
│   │   └── alerts.ts
│   │
│   ├── types/
│   ├── public/
│   ├── package.json
│   └── .env.local.example
│
├── backend/
│   ├── config/
│   ├── apps/
│   │   ├── accounts/
│   │   ├── products/
│   │   ├── categories/
│   │   ├── brands/
│   │   ├── cart/
│   │   ├── orders/
│   │   ├── customers/
│   │   ├── coupons/
│   │   ├── reviews/
│   │   ├── inventory/
│   │   ├── notifications/
│   │   ├── payments/
│   │   └── reports/
│   ├── media/
│   ├── requirements.txt
│   ├── manage.py
│   ├── .env.example
│   └── venv/
│
├── database/
│   ├── migrations/ 
│   └── seeds/
==============================================
Admin Collapsible sidebar
Admin Responsive mobile layout

Admin routes:
Route
/admin/login - Admin authentication
/admin/dashboard - Dashboard analytics
/admin/products - Product management
/admin/orders - Order management
/admin/customers - Customer management
/admin/categories - Category management
/admin/brands - Brand management
/admin/coupons - Coupon management
/admin/reviews - Review moderation
/admin/users - Admin and staff management
/admin/settings - Store settings
/admin/notifications - Notification center
/admin/files - Media and file manager
/admin/reports - Sales and inventory reports
==============================================
Authentication Module
Implement:

- Login
- Logout
- Remember Me
- Forgot Password
- Reset Password
- Change Password
- Role Based Access Control (RBAC)
- Login History
- Secure Login
- User Profile Management
- Use secure password hashing such as bcrypt   
- CSRF protection
- XSS Protection
- Session management
- SQL injection protection using PDO prepared statements
- Input validation and sanitization

Dashboard http://localhost:3000/admin/dashboard
Features:
Display real-time statistics:
Total Revenue
Net Earning
Today Order
Total products
Yesterday Orders
Total Order
Total customers
Low-stock products
Revenue analytics
Sales Analytic
Best Selling Products
Recent Order in table with photo of product
Use charts (Chart.js) for dashboard stats
Use Chart.js for all charts.
------------------------------------
User Management

- CRUD Users
- Roles
- Permissions
- User Activity Log
- User Status
- User Profile Picture
------------------------------------
Products Management Module
Features:
header dashboard (total products, active listing, draft products, out of stock, inventory units)
Products (Manage your products inventory)
-export (export to CSV, export to json)
View all Products (paginated, searchable)
Add Products (new page, Upload multiple product images,text editor)
Edit Products details (update photo)
View Product (Product Details page, photo large left right information with edit button)
Delete Products (delete photo)  
Manage cost and selling prices
Manage stock quantities
Manage minimum stock levels
Activate and deactivate products
------------------------------------
Orders Management Module
Features:
Manage customer orders - Download all orders in csv file
header dashboard (Total Orders, open orders, paid orders, total revenue, average order value)
View all Orders (order, customer, date, payment, Fullfillment, items, net sale, action, paginated, searchable)
Edit Order
Orders details
Order Tracking
Delete Orders
print receipt
------------------------------------
Customers Management Module
Features:
View all Customers (paginated, searchable)
Create new Customers
Edit Customers details
view (new page Customer Order List table)
Delete Customers
Activate and deactivate customer accounts
------------------------------------
Category Management Module
Features:
View all categories (paginated, searchable)
Create new categories
Edit categories details
Delete categories
====================================
Brands Management Module
Features:
View all brands (paginated, searchable)
Create new brands
Edit brands details
Delete brands
=====================================
Coupons Management Module
Features:
View all coupons (paginated, searchable)
Create new coupons
Edit coupons details
Delete coupons
======================================
Settings Management Module
Features:
View all settings (paginated, searchable)
Create new settings
Edit settings details
Delete settings
=======================================
Reviews Management Module
Features:
View all reviews (paginated, searchable)
Edit reviews details
Delete reviews
======================================
Notification System
Toast Notifications
Email Notifications
SMS Ready
In-app Notifications
------------------------------------
Inventory Management
Stock tracking.
Stock adjustments.
Stock movement history.
Stock-in transactions.
Stock-out transactions.
Low-stock alerts.
Inventory valuation.
Product stock reports.
Use FullCalendar to display stock-related events, purchase schedules, and important inventory activities.
--------------------------------------
File Manager
Upload Documents
Images
Contracts
Invoices
Customer Files
------------------------------------
Settings Module
Company Settings
SMTP Settings
Currency
Language
Timezone
Theme
Logo
Backup
-------------------------------------
Professional Admin Dashboard
Responsive
Mobile Friendly
Dark Mode Ready
Loading Spinners
Skeleton Loaders
Modern Cards
Beautiful Tables
Animations
Hover Effects
------------------------------------
DataTables
Include:
Server-side Processing
Sorting
Searching
Filtering
Export Buttons
Print
CSV
Excel
PDF
------------------------------------
SweetAlert2
Use for:
Delete Confirmation
Success Messages
Errors
Warnings
Confirmations
------------------------------------
Build RESTful APIs using Django REST Framework.
API base URL:
/api/v1/
Example endpoints:
Authentication:
POST /api/v1/auth/register/
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/
GET /api/v1/auth/profile/

Products:
GET /api/v1/products/
GET /api/v1/products/{id}/
POST /api/v1/products/
PUT /api/v1/products/{id}/
PATCH /api/v1/products/{id}/
DELETE /api/v1/products/{id}/

Categories:
GET /api/v1/categories/
POST /api/v1/categories/
PUT /api/v1/categories/{id}/
DELETE /api/v1/categories/{id}/

Brands:
GET /api/v1/brands/
POST /api/v1/brands/
PUT /api/v1/brands/{id}/
DELETE /api/v1/brands/{id}/

Orders:
GET /api/v1/orders/
POST /api/v1/orders/
GET /api/v1/orders/{id}/
PATCH /api/v1/orders/{id}/status/

Customers:
GET /api/v1/customers/
GET /api/v1/customers/{id}/
PATCH /api/v1/customers/{id}/

Inventory:
GET /api/v1/inventory/
POST /api/v1/inventory/adjust/
GET /api/v1/inventory/movements/

Coupons:
GET /api/v1/coupons/
POST /api/v1/coupons/
POST /api/v1/coupons/validate/

Reports:
GET /api/v1/reports/dashboard/
GET /api/v1/reports/sales/
GET /api/v1/reports/products/
GET /api/v1/reports/inventory/

Implement:
Serializers.
ViewSets and API views.
URL routing.
Pagination.
Filtering.
Search.
Ordering.
Validation.
Permission classes.
Consistent API responses.
API documentation using drf-spectacular.
-----------------------------------------
SECURITY REQUIREMENTS

Implement:
JWT authentication.
Secure password hashing.
Role-based permissions.
Object-level authorization where required.
Input validation.
CORS configuration.
CSRF protection.
Rate limiting for sensitive endpoints.
Secure file uploads.
File type and size validation.
Environment variable protection.
SQL injection prevention through Django ORM.
XSS protection.
Secure production settings.
Audit logs for important admin actions.
Never expose Django secret keys, database passwords, or payment secrets in frontend code.
-----------------------------------------------------------------------
Create a premium E-Commerce Home Industrial Tool homepage http://localhost:3000/

- Sticky transparent header
- theme
- Wishlist
- Sign and register
- Cart drawer

Sections:
Navigation Structure
Top Navigation
    Home
    Shop
    categories
    Brands
    Contact
Right Side Icons
    Search
    theme
    Wishlist
    Cart
    signin register
Wishlist
    Heart icon
    Hover counter
    Saved products

1. hero section
   - 3 featured product
   - luxury headline
   - 2 button shop the catalog and browse categories

2. Feature icons row
   - Free Shipping
   - Easy Returns
   - Secure Checkout

3. Shop By Category
   - 6 category cards
   - image zoom hover

4. Products on Sale
   - 4 column product grid
   - wishlist
   - quick view
   - hover image swap

5. Promotional Banner
   - split layout
   - premium storytelling section

6. New Arrivals
   - modern ecommerce cards

7. Top Deals
   - countdown timer
   - featured product card
   - add to cart
   - variant selector

8. Featured Products
   - luxury banner
   - CTA buttons

9. SHOP BY BRAND

10. Customer Reviews
   - auto sliding testimonials

11. Large Footer
   - 4 columns
   - newsletter
   - social icons

Animations:
- smooth fade-up on scroll
- image zoom hover
- cart drawer slide
- mega menu dropdown animation
- button hover transitions
==================================================
Create a customer login signup page for customer http://localhost:3000/login and http://localhost:3000/register
==================================================
after login and signup redirect to my account page 
Create a customer my account http://localhost:3000/account
with landing-navigation and landing-footer 
Dashboard
    -overview (Total Orders, Pending Orders, Wishlist items,total spent, Recent Orders datatable)
    -my order (My Orders, track and manage your orders)
    -notifications
    -my cart 
    -wishlist
Settings   
    -profile
    -billing address 
    -security 
    -login history
Sign Out  
===================================================
Create product page all http://localhost:3000/products
create all categories page http://localhost:3000/categories
create all brand page http://localhost:3000/brands

1 Design Style:
    Subtle shadows and soft borders
    Smooth hover animations and transitions

    Main Layout Structure:

    Use a two-column layout
    Left sidebar for filters
    Right content area for products

 2  Sidebar Filter Section:
    Include:

    Product categories
    Brand filters
    Price range

    Sidebar Design:

    cards with soft shadow
    Sticky sidebar on desktop
    Accordion sections
    Thin dividers
    Modern checkbox styling
    Minimal icon usage

    Top Toolbar Section:
    Include:

    Product count text
    Sorting dropdown
    Grid/list toggle buttons
    Search input optional
    Clean horizontal alignment
    Subtle bottom border

    Product Grid:

    3 or 4-column responsive card layout
    Equal card heights
    Consistent spacing and alignment
    Masonry-like visual rhythm without actual masonry

3 Product Card Design:
    Each card should include:

    Product image
    Hover image swap
    Sale badge / discount badge
    Wishlist icon
    Quick view button
    Product category
    Product title
    Star ratings
    Current price
    Old price
    Add to cart button

    Card UI:

    Rounded corners
    Soft shadow
    Hover lift animation
    Image zoom on hover
    Buttons fade in on hover
    Clean typography
    Modern ecommerce interactions
4. url link http://localhost:3000/products/{slug} product slug    
===================================================
Create a product page details http://localhost:3000/products/werner-nitrile-grip-gloves {slug} from products database 

1. Product Showcase Section
Two-column responsive layout
Large product gallery on the left
Product information panel on the right
Sticky product image gallery behavior on scroll
Vertical thumbnail gallery beside main image
Smooth image switching interaction
Light zoom-on-hover effect
Large clean product imagery with soft gray background container

2. Product Information Area
Include:
Product category label
Large bold product title
Rating stars with review count
Pricing layout with sale price + original price
Short product description paragraph
Quantity selector with plus/minus buttons
Large primary “Add to Cart” button
Wishlist and compare icons
SKU/meta information

3. Product Details Tabs Section
Tabbed content layout with:
Description
Specifications
Reviews

Tab Design:

Minimal horizontal tab navigation
Active tab underline animation
Smooth content transitions
Large readable content spacing

5. Related Products Section (You may also like)
Grid layout with 4 related products
Card-based design
Hover image swap effect
Floating action buttons on hover
Product badges like “Sale” or “New”
Consistent product card spacing
Minimal typography hierarchy  
=================================================
payment http://localhost:3000/checkout
install https://docs.stripe.com/get-started/development-environment?lang=node stripe 
install https://developer.paypal.com/sdk/payouts PayPal Checkout 