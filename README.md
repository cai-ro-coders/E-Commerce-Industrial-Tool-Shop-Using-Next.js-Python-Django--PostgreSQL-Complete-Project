# TorqueForge Industrial Supply

A full-stack e-commerce application for an industrial tool shop, with a customer
storefront and a complete role-based admin panel.

- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS v4
- **Backend:** Django, Django REST Framework, Simple JWT, PostgreSQL
- **Admin features:** dashboard analytics, products, orders, customers, categories,
  brands, coupons, reviews, users, inventory, notifications, files, reports, settings
- **Storefront features:** product catalog, search, cart, wishlist, checkout,
  coupons, customer account, order tracking

---

## Table of Contents

1. [Requirements](#requirements)
2. [Project Structure](#project-structure)
3. [Installation](#installation)
   - [1. PostgreSQL Database](#1-postgresql-database)
   - [2. Backend Setup](#2-backend-setup)
   - [3. Seed Demo Data](#3-seed-demo-data)
   - [4. Frontend Setup](#4-frontend-setup)
4. [Demo Accounts](#demo-accounts)
5. [Application URLs](#application-urls)
6. [Stripe Payments](#stripe-payments)
7. [PayPal Payments](#paypal-payments)
8. [Admin Panel Routes](#admin-panel-routes)
9. [API Reference](#api-reference)
10. [Running Tests](#running-tests)
11. [Useful Commands](#useful-commands)
12. [Security Notes](#security-notes)
12. [Troubleshooting](#troubleshooting)

---

## Requirements

| Tool | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 20.9+ (24.x recommended) |
| npm | 10+ |
| PostgreSQL | 14+ |

> The backend virtualenv in this project uses Python 3.12, Django 6.1,
> DRF 3.18, and PostgreSQL via `psycopg2-binary`.

---

## Project Structure

```text
ecommerce_industrial_tool/
├── backend/
│   ├── apps/
│   │   ├── accounts/       # users, auth, addresses, activity/login history
│   │   ├── brands/
│   │   ├── cart/           # cart items, wishlist
│   │   ├── categories/
│   │   ├── core/           # settings, file manager, pagination, seed command, tests
│   │   ├── coupons/
│   │   ├── customers/
│   │   ├── inventory/
│   │   ├── notifications/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── products/
│   │   └── reviews/
│   ├── backend/            # Django project (settings.py, urls.py)
│   ├── media/              # uploaded product images and files
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   └── venv/
├── frontend/
│   ├── app/
│   │   ├── (storefront)/   # public shop pages
│   │   └── admin/          # admin login and panel
│   ├── components/
│   ├── hooks/
│   ├── lib/                # API client, auth, utilities
│   ├── package.json
│   └── .env.local.example
├── AI.md                   # Original project specification
└── README.md
```

---

## Installation

### 1. PostgreSQL Database

Create the database and user used by `backend/.env`:

```bash
psql -U postgres -c "CREATE USER postgresdb WITH PASSWORD 'cairocoders';"
psql -U postgres -c "CREATE DATABASE ecommerce OWNER postgresdb;"
```

If the role already exists, set its password instead:

```bash
psql -U postgres -c "ALTER USER postgresdb WITH PASSWORD 'cairocoders';"
```

Verify the connection:

```bash
psql -U postgresdb -d ecommerce -h localhost -c "SELECT 1;"
```

Credentials used by this project:

| Setting | Value |
|---|---|
| Database | `ecommerce` |
| User | `postgresdb` |
| Password | `cairocoders` |
| Host | `localhost` |
| Port | `5432` |

> On macOS with Postgres.app or Homebrew, the superuser is usually your macOS
> username rather than `postgres`. In that case use `psql postgres -c "..."`.

---

### 2. Backend Setup

From the project root:

```bash
cd backend
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Edit `backend/.env` and set at minimum:

```env
DJANGO_SECRET_KEY=replace-with-a-long-random-string
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=ecommerce
DB_USER=postgresdb
DB_PASSWORD=cairocoders
DB_HOST=localhost
DB_PORT=5432

CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
FRONTEND_URL=http://localhost:3000
```

Run migrations:

```bash
python manage.py migrate
```

Start the backend server:

```bash
python3 manage.py runserver
```

The API is now available at **http://localhost:8000/api/v1/**.

---

### 3. Seed Demo Data

The project includes a seed command that creates realistic demo categories,
brands, products, orders, reviews, coupons, inventory logs, notifications,
settings, and demo users.

```bash
cd backend
source venv/bin/activate
python manage.py seed_data
```

The command is idempotent. To wipe the demo data first and reseed:

```bash
python manage.py seed_data --reset
```

> `--reset` deletes non-superuser users, products, orders, and related demo
> records. Do not run it against a production database.

Create an additional Django superuser for `/django-admin/` if needed:

```bash
python manage.py createsuperuser
```

---

### 4. Frontend Setup

Open a second terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create the environment file:

```bash
cp .env.local.example .env.local
```

Confirm `frontend/.env.local` contains:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_SITE_NAME=TorqueForge Industrial Supply
```

Start the development server:

```bash
npm run dev
```

The storefront is now available at **http://localhost:3000/**.

For a production build:

```bash
npm run build
npm start
```

---

## Demo Accounts

The demo accounts below are created by `python manage.py seed_data`.

### Admin (full access)

| Field | Value |
|---|---|
| Admin panel | **http://localhost:3000/admin/login** |
| Email | **`admin@industrialtools.com`** |
| Password | **`Admin@12345`** |
| Role | `admin` |

The admin account is also a Django superuser, so it can access
**http://localhost:8000/django-admin/**.

### Staff

| Field | Value |
|---|---|
| Admin panel | http://localhost:3000/admin/login |
| Email | `staff@industrialtools.com` |
| Password | `Staff@12345` |
| Role | `staff` |

### Customer

| Field | Value |
|---|---|
| Storefront login | http://localhost:3000/login |
| Email | `customer@example.com` |
| Password | `Customer@12345` |
| Role | `customer` |

> These credentials are for local development only. Change or remove all demo
> accounts before deploying to production.

---

## Application URLs

| Page | URL |
|---|---|
| Storefront | http://localhost:3000/ |
| Products | http://localhost:3000/products |
| Customer login | http://localhost:3000/login |
| Customer registration | http://localhost:3000/register |
| Customer account | http://localhost:3000/account |
| Cart | http://localhost:3000/cart |
| Checkout | http://localhost:3000/checkout |
| Admin login | http://localhost:3000/admin/login |
| Admin dashboard | http://localhost:3000/admin/dashboard |
| API root | http://localhost:8000/api/v1/ |
| API docs (Swagger UI) | http://localhost:8000/api/docs/ |
| API schema (OpenAPI) | http://localhost:8000/api/schema/ |
| Django admin | http://localhost:8000/django-admin/ |

---

## Customer Account Dashboard

`/account` is the signed-in customer dashboard. The sidebar groups features into:

| Section | Tab | What it does |
|---|---|---|
| Dashboard | Overview | Total orders, pending orders, wishlist items, total spent, and a recent-orders table |
| Dashboard | My Orders | Search/filter orders and open any order to track it or print a receipt |
| Dashboard | Notifications | All/unread filters, mark one or all as read |
| Dashboard | My Cart | Update quantities, remove items, clear the cart, and continue to checkout |
| Dashboard | Wishlist | Remove saved items or move them into the cart |
| Settings | Profile | Update name, phone, and avatar |
| Settings | Billing address | Create, edit, delete, and set a default address |
| Settings | Security | Change password (bcrypt-hashed) |
| Settings | Login history | Recent sign-in attempts with IP address and device |
| — | Sign out | Ends the session and returns to the storefront |

Dashboard counts come from `GET /api/v1/auth/account-summary/`, which only
returns data for the authenticated customer.

---

## Stripe Payments

The storefront checkout supports Stripe card payments through the Stripe
Payment Element. Stripe keys are **not** stored in `.env`; they live in the
database and are managed from the admin panel.

### 1. Add your keys

1. Sign in at http://localhost:3000/admin/login.
2. Open **Settings → Payments**.
3. Paste your keys from the Stripe Dashboard
   (https://dashboard.stripe.com/test/apikeys):
   - **Stripe publishable key** — `pk_test_…` (or `pk_live_…`)
   - **Stripe secret key** — `sk_test_…` (or `sk_live_…`)
   - **Stripe webhook signing secret** — `whsec_…` (optional in development,
     required for webhook verification)
4. Save the Payments group.

The secret key is only read server-side. `GET /api/v1/settings/public/` never
returns payment settings, and the checkout only receives the publishable key.

### 2. Checkout flow

1. Customer selects **Stripe** as the payment method and clicks
   **Continue to payment**.
2. `POST /api/v1/orders/` creates the order and clears the cart, then the
   browser navigates to `/checkout/stripe?order={id}`.
3. `POST /api/v1/payments/stripe/create-intent/` creates a PaymentIntent for
   the order total using the database secret key and returns its `client_secret`.
4. The dedicated Stripe payment step renders the Payment Element; Stripe.js
   collects the card details and confirms the payment.
5. `POST /api/v1/payments/stripe/confirm/` verifies the PaymentIntent with
   Stripe and marks the order and payment as paid.
6. Pending Stripe orders also show a **Pay now** button on the order page,
   which opens the same `/checkout/stripe?order={id}` step so a customer can
   retry an abandoned payment.

Test cards: `4242 4242 4242 4242`, any future expiry date, any CVC.

### 3. Webhooks (recommended)

For local development, forward Stripe events with the Stripe CLI:

```bash
stripe listen --forward-to localhost:8000/api/v1/payments/stripe/webhook/
```

Copy the printed `whsec_…` value into **Settings → Payments → Stripe webhook
signing secret**. In production, add the same URL as a webhook endpoint in the
Stripe Dashboard and subscribe to `payment_intent.succeeded`,
`payment_intent.payment_failed`, and `payment_intent.canceled`.

The synchronous confirm endpoint gives the customer immediate feedback, while
the webhook remains the source of truth for asynchronous payment events.

---

## PayPal Payments

The checkout also supports PayPal through the PayPal JS SDK (Orders v2). Like
Stripe, credentials are stored in the database and managed from the admin
panel — they are never placed in `.env`.

### 1. Add your credentials

1. Sign in at http://localhost:3000/admin/login.
2. Open **Settings → Payments**.
3. Enter the credentials from the PayPal Developer Dashboard
   (https://developer.paypal.com/dashboard/applications):
   - **PayPal client ID** — the public app client ID
   - **PayPal client secret** — the private app secret
   - **PayPal mode** — `sandbox` for testing, `live` for production
4. Save the Payments group.

The client secret is only read server-side. `GET /api/v1/settings/public/`
never returns payment settings, and the browser only receives the public client
ID plus short-lived PayPal order IDs.

### 2. Checkout flow

1. Customer selects **PayPal** as the payment method and clicks
   **Continue to PayPal**.
2. `POST /api/v1/orders/` creates the order and clears the cart, then the
   browser navigates to `/checkout/paypal?order={id}`.
3. `POST /api/v1/payments/paypal/create-order/` creates a PayPal Order for the
   order total using the database credentials and returns its ID.
4. The dedicated PayPal step renders the PayPal buttons; the customer approves
   the payment in the PayPal window.
5. `POST /api/v1/payments/paypal/capture/` captures the PayPal Order, verifies
   the custom ID, amount, and currency, then marks the order and payment as
   paid.
6. Pending PayPal orders also show a **Pay with PayPal** button on the order
   page, which opens the same `/checkout/paypal?order={id}` step so a customer
   can retry an abandoned payment.

Use a PayPal sandbox personal account to test. The checkout shows the active
mode (sandbox/live) next to the amount due.

---

## Admin Panel Routes

All admin pages require an authenticated `admin` or `staff` user.

| Module | Route |
|---|---|
| Login | `/admin/login` |
| Dashboard | `/admin/dashboard` |
| Products | `/admin/products` |
| Orders | `/admin/orders` |
| Customers | `/admin/customers` |
| Categories | `/admin/categories` |
| Brands | `/admin/brands` |
| Coupons | `/admin/coupons` |
| Reviews | `/admin/reviews` |
| Users | `/admin/users` |
| Inventory | `/admin/inventory` |
| Reports | `/admin/reports` |
| Notifications | `/admin/notifications` |
| Files | `/admin/files` |
| Settings | `/admin/settings` |
| Profile | `/admin/profile` |

---

## API Reference

Base URL: `http://localhost:8000/api/v1/`
Example :  http://localhost:8000/api/v1/categories/

Authentication uses JWT bearer tokens:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@industrialtools.com","password":"Admin@12345"}'
```

Use the returned access token:

```bash
curl http://localhost:8000/api/v1/products/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

Key endpoints:

| Resource | Endpoints |
|---|---|
| Auth | `POST /auth/register/`, `POST /auth/login/`, `POST /auth/refresh/`, `POST /auth/logout/`, `GET/PATCH /auth/profile/`, `POST /auth/change-password/`, `GET /auth/login-history/`, `GET /auth/account-summary/` |
| Products | `GET/POST /products/`, `GET/PUT/PATCH/DELETE /products/{id}/` |
| Categories | `GET/POST /categories/`, `GET/PUT/PATCH/DELETE /categories/{id}/` |
| Brands | `GET/POST /brands/`, `GET/PUT/PATCH/DELETE /brands/{id}/` |
| Orders | `GET/POST /orders/`, `GET/PATCH /orders/{id}/`, `PATCH /orders/{id}/status/` |
| Payments | `GET /payments/`, `GET /payments/stripe/config/`, `POST /payments/stripe/create-intent/`, `POST /payments/stripe/confirm/`, `POST /payments/stripe/webhook/`, `GET /payments/paypal/config/`, `POST /payments/paypal/create-order/`, `POST /payments/paypal/capture/` |
| Customers | `GET /customers/`, `GET/PATCH /customers/{id}/` |
| Inventory | `GET /inventory/`, `POST /inventory/adjust/`, `GET /inventory/movements/` |
| Coupons | `GET/POST /coupons/`, `POST /coupons/validate/` |
| Reports | `GET /reports/dashboard/`, `/reports/sales/`, `/reports/products/`, `/reports/inventory/` |

Paginated list responses use the shape:

```json
{
  "success": true,
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 0,
    "total_pages": 0,
    "next": null,
    "previous": null,
    "timestamp": "2026-01-01T00:00:00+00:00"
  }
}
```

Interactive documentation with request/response schemas is available at
**http://localhost:8000/api/docs/**.

---

## Running Tests

Backend API test suite (68 tests covering auth, RBAC, CRUD, orders, inventory,
notifications, reports, and response envelopes):

```bash
cd backend
source venv/bin/activate
python manage.py test
```

Frontend type check:

```bash
cd frontend
npx tsc --noEmit
```

Production build:

```bash
cd frontend
npm run build
```

---

## Useful Commands

```bash
# Backend
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data
python manage.py seed_data --reset
python manage.py test
python manage.py createsuperuser
python3 manage.py runserver

# Frontend
npm run dev
npm run build
npm start
npm run lint
npx tsc --noEmit
```

---

## Security Notes

Implemented safeguards include:

- JWT access/refresh tokens with rotation and blacklisting
- bcrypt password hashing (`BCryptSHA256PasswordHasher`)
- Role-based access control and object-level permissions
- Login history and audit activity logs
- Rate limiting on login, registration, password reset, and coupon validation
- CORS and CSRF configuration driven by environment variables
- Input validation through DRF serializers and Zod
- Upload size limits (10 MB) and media handling through Django
- Secrets loaded from `.env` and never exposed to the frontend

For production:

1. Set `DJANGO_DEBUG=False`.
2. Generate a new `DJANGO_SECRET_KEY` and use strong database credentials.
3. Set `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` to real domains.
4. Serve the app over HTTPS.
5. Configure SMTP for password-reset and notification emails.
6. Remove demo accounts and reseed only the data you need.
7. Serve `media/` and `static/` through your web server or object storage.

---

## Troubleshooting

**`connection refused` or `password authentication failed` for PostgreSQL**

Confirm PostgreSQL is running and that the `ecommerce` database and `postgresdb`
user exist with the password in `backend/.env`.

```bash
psql -U postgresdb -d ecommerce -h localhost -c "SELECT 1;"
```

**`ModuleNotFoundError` during `seed_data` or `runserver`**

The virtualenv is not active or dependencies are missing:

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

**`ImportError: incompatible architecture` on Apple Silicon**

This happens when the Python interpreter and a native package (for example
`psycopg2` or `Pillow`) use different architectures. Rebuild the virtualenv
with the same Python that will run the server:

```bash
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Do not mix a Rosetta/x86_64 terminal with an arm64 virtualenv, or vice versa.

**Port already in use**

Run on a different port and update `NEXT_PUBLIC_API_URL` accordingly:

```bash
python manage.py runserver 8001
npm run dev -- -p 3001
```

**Frontend native module / lightningcss error**

If the error mentions `lightningcss.darwin-arm64.node`, `oxide`, or an
incompatible architecture, the installed Node.js and `node_modules` do not
match. Reinstall dependencies with the same Node.js installation used to run
the app:

```bash
cd frontend
rm -rf node_modules .next
npm ci
npm run dev
```

For other cache-related build errors, clearing `.next` is usually enough:

```bash
cd frontend
rm -rf .next
npm run dev
```

**Media or product images return 404**

With `DJANGO_DEBUG=True`, Django serves `backend/media/`. In production, configure
your web server or CDN to serve the media directory.

---

## License

This project is provided for demonstration and educational purposes.
