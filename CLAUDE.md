# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL RULES

**PRESERVE PROJECT STRUCTURE**: Do NOT reorganize, rename, or restructure the existing project layout. Maintain the current directory structure, file organization, and naming conventions. Any new files should follow existing patterns.

## Project Overview

This is a **Django 5.0.1 Daycare Management System** called "PolymathDayCare" that handles:
- Child enrollment and management
- Package pricing and billing (Fixed & Flexible packages)
- Attendance tracking via QR codes
- Invoice memo generation (3-month rolling system)
- Holiday and rate management
- Branch and center management
- Approval workflows (Enrollments, Discounts, Package/Center changes)

## Project Structure (DO NOT MODIFY)

```
PolymathDayCare/
├── daycareSystem/           # Django project configuration
│   ├── settings.py          # Main settings (MySQL, sessions, CORS)
│   ├── urls.py              # Root URL routing
│   ├── wsgi.py              # WSGI application
│   └── asgi.py              # ASGI application
├── core/                    # Main application (ALL business logic)
│   ├── models.py            # 27 Django models
│   ├── views.py             # 196 view functions (~15K lines)
│   ├── urls.py              # 100+ URL patterns
│   ├── forms.py             # Django forms
│   ├── admin.py             # Admin interface
│   └── migrations/          # Database migrations
├── transactions/            # Placeholder for future financial transactions
│   ├── models.py            # Empty
│   └── views.py             # Empty
├── templates/               # HTML templates
│   ├── base.html            # Main layout (Bootstrap 5 + ApexCharts)
│   ├── login.html           # Authentication
│   ├── partials/            # Reusable form components
│   ├── reports/             # Report templates
│   └── utils/               # Data import utilities
├── static/assets/           # Static assets
│   ├── css/                 # Bootstrap + custom CSS
│   ├── js/                  # jQuery, DataTables, ApexCharts
│   ├── images/              # Logos and images
│   ├── fonts/               # Web fonts
│   └── libs/                # Third-party libraries
├── media/                   # User-generated content
│   ├── child_images/        # Child profile pictures
│   ├── enrollment_forms/    # Generated enrollment PDFs
│   └── qr/                  # QR code images
├── manage.py                # Django management utility
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (not in git)
```

## Development Commands

### Running the Application
```bash
# Activate virtual environment (Windows)
env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Run development server
python manage.py runserver

# Create superuser
python manage.py createsuperuser
```

### Database Operations
```bash
# Create migrations for specific app
python manage.py makemigrations core
python manage.py makemigrations transactions

# Apply migrations
python manage.py migrate

# Reset database (careful!)
python manage.py flush
```

### Static Files
```bash
# Collect static files for production
python manage.py collectstatic
```

### Testing
```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test core
python manage.py test transactions

# Run with verbosity
python manage.py test --verbosity=2

# Keep test database (faster subsequent runs)
python manage.py test --keepdb
```

### Code Quality & Linting
```bash
# Format code with Ruff
ruff format .

# Lint and auto-fix
ruff check . --fix

# Type checking
mypy core/ transactions/
```

## Database Models (core/models.py)

### Model Hierarchy (27 Models)

**Base Infrastructure:**
| Model | Purpose |
|-------|---------|
| `BaseClass` | Abstract base with audit fields (id, dates, user tracking, is_active) |
| `Branch` | Physical locations/headquarters |
| `DayCare` | Centers within branches (called "Center" in UI) |
| `PackageType` | Normal vs Holiday classification |
| `PackageTerm` | Fixed vs Dynamic packages |

**Child Management:**
| Model | Purpose |
|-------|---------|
| `Child` | Core child info with QR codes, images, contact details |
| `ChildEnrollment` | Enrollment workflow with approval (PENDING/APPROVED/REJECTED) |
| `ChildPackageMapping` | Links children to packages with effective date ranges |

**Package & Pricing:**
| Model | Purpose |
|-------|---------|
| `FixedPackage` | Time-based packages (e.g., 8AM-12PM) with auto-calculated hours |
| `FlexPackages` | Hour-based flexible pricing |
| `ExtraHoursAfter530` | Extra charges after 5:30 PM |
| `ExtraHoursUpTo530` | Extra charges until 5:30 PM |
| `PackageExtraHoursMapping` | Links packages to extra hour rates |
| `Discount` | Discount codes with approval workflow |
| `ExtraChargesHistory` | Historical tracking of rate changes |

**Holiday Management:**
| Model | Purpose |
|-------|---------|
| `Holiday` | Holiday definitions with auto day counting (weekdays/weekends) |

**Workflow Requests:**
| Model | Purpose |
|-------|---------|
| `PackageChangerequest` | Package upgrade/downgrade approvals |
| `CenterChangerequest` | Center transfer approvals |

**Attendance & Billing:**
| Model | Purpose |
|-------|---------|
| `AttendanceLog` | QR code-based daily check-ins |
| `EnrollmentForm` | Generated enrollment PDF documents |
| `InvoiceMemo` | Main invoice summary (one per child per month) |
| `InvoiceMemoDetail` | Month breakdown (exactly 3 per memo: Outstanding/Previous/Current) |
| `PaymentTransaction` | Payment records with receipt tracking |

### Key Relationships
- Most models extend `BaseClass` for consistent auditing
- Foreign keys use CASCADE deletion (be careful with deletions)
- `InvoiceMemo` always has exactly 3 `InvoiceMemoDetail` records
- `ChildPackageMapping` has unique constraint on (child, effective_from date range)

## URL Structure (core/urls.py)

### Major URL Patterns (100+)

| Feature | URLs |
|---------|------|
| **Authentication** | `/login/`, `/logout/` |
| **Dashboard** | `/` (home) |
| **Children** | `/child/`, `/savechild/`, `/deletechild/<id>/` |
| **Packages** | `/fixed_packages/`, `/flex_packages/`, `/package_types/` |
| **Rates** | `/additional_rates/`, `/additional_rates_upto530/` |
| **Branches/Centers** | `/branches/`, `/daycare/` |
| **Holidays** | `/public_holidays/`, `/polymath_holidays/`, `/other_holidays/` |
| **Enrollments** | `/enrollments/`, `/save_enrollments/`, `/approve_enrollments/` |
| **Attendance** | `/check_ins/`, `/checkInView/<admission_no>/`, `/upload_csv/` |
| **Invoices** | `/memo_data_entry/`, `/load_invoice_memo/`, `/search_invoice_memo/` |
| **Payments** | `/apply_payment/`, `/process_payment/`, `/search_memo_for_payment/` |
| **Reports** | `/attendenceReport/`, `/extra_hours_report/` |
| **Package Changes** | `/get_package_change/`, `/package_change_approval/` |
| **Center Changes** | `/center_change_request/` |

## Configuration

### Environment Variables (.env)
```
SECRET_KEY=<django-secret-key>
DEBUG=True
DB_NAME=polymath_core
DB_USER=root
DB_PASSWORD=<password>
DB_HOST=localhost
DB_PORT=3306
PROD_URL=https://dc.polymathcore.online/
QR_METHOD_NAME=checkInView
```

### Database Configuration
- **Engine**: MySQL via `django.db.backends.mysql`
- **Driver**: mysqlclient 2.2.4
- **Tables**: Prefixed with `dc_` (daycare)
- **Timezone**: Asia/Colombo

### Session Configuration
- **Timeout**: 50 minutes (SESSION_COOKIE_AGE = 3000)
- **Extension**: Extended on each request
- **Expiration**: On browser close

## Key Business Logic

### 1. QR Code Attendance System
```
Child Creation → Auto-generate QR code
QR URL Format: {PROD_URL}/{QR_METHOD_NAME}/{admission_number}/
Example: https://dc.polymathcore.online/checkInView/ADM001/
Scan QR → Logs attendance (one per child per day)
```

### 2. Three-Month Invoice System
```
InvoiceMemo (Summary)
├── InvoiceMemoDetail (OUTSTANDING - 2 months ago)
├── InvoiceMemoDetail (PREVIOUS - last month)
└── InvoiceMemoDetail (CURRENT - this month)

Each detail contains:
- Charges: package_fee, extra_hours_charge, holiday_charges, other_charges
- Deductions: discount_applied, other_deductions
- Calculated: gross_charges, total_deductions, net_charges
- Payments: payments_received, payment_receipts (JSON)
- Balance: net_balance
```

### 3. Hierarchical Payment Allocation
```
Payment received → Apply to OUTSTANDING first
                → Then PREVIOUS
                → Then CURRENT
                → Excess becomes credit
```

### 4. Approval Workflows (3-State)
```
PENDING_APPROVAL → APPROVED
                 → REJECTED

Applied to: Enrollments, Discounts, Package Changes, Center Changes
```

### 5. Package Pricing
- **FixedPackage**: Time-based (8AM-12PM), auto-calculates hours
- **FlexPackage**: Hour-based flexible pricing
- **Extra Hours**: Two tiers (before/after 5:30 PM)
- **Holiday Packages**: Special pricing during holidays

### 6. Holiday Impact on Billing
- Holidays exclude from normal billing
- Holiday packages charge instead (if active)
- Auto-counts weekdays/weekends in date range

## Views Overview (core/views.py)

### Statistics
- **Total Functions**: 196
- **Total Lines**: ~15,000
- **Pattern**: Function-based views with @login_required decorator

### Key View Categories
| Category | Count | Examples |
|----------|-------|----------|
| Authentication | 4 | `UserLogin`, `UserLogOut`, `index` |
| Child Management | 7 | `getChild`, `createChild`, `getChildJson` |
| Package Management | 20+ | `getFixedPackages`, `saveFlexPackage` |
| Attendance | 10 | `getCheckIns`, `autoAttendanceRecorder` |
| Invoice/Billing | 25+ | `getMemoDataEntry`, `saveMemoDataEntry` |
| Payments | 10+ | `process_payment`, `get_apply_payment_page` |
| Reports | 5+ | `getAttendanceReports`, `getExtraHoursReport` |

## Templates Structure

### Main Templates (30+)
- `base.html` - Master layout (Bootstrap 5, ApexCharts, DataTables)
- Feature templates: `child.html`, `enrollment.html`, `invoice.html`, etc.
- `templates/partials/` - Reusable update forms
- `templates/reports/` - Report templates

### Frontend Stack
- Bootstrap 5 (responsive layout)
- jQuery (AJAX operations)
- DataTables (data display with pagination)
- Select2 (enhanced dropdowns)
- Flatpickr (date picking)
- ApexCharts (data visualization)

## Common Development Tasks

### Adding a New Feature
1. Add model to `core/models.py` (extend `BaseClass`)
2. Create migration: `python manage.py makemigrations core`
3. Apply migration: `python manage.py migrate`
4. Add views to `core/views.py`
5. Add URL patterns to `core/urls.py`
6. Create template in `templates/`
7. Register in `core/admin.py` if needed

### Adding New Package Types
1. Create in `PackageType` model
2. Configure in `FixedPackage` or `FlexPackages`
3. Set up extra hours mapping in `PackageExtraHoursMapping`

### Generating Invoices
1. Navigate to memo data entry interface
2. Select child and month
3. System auto-calculates based on attendance
4. Creates `InvoiceMemo` with 3 `InvoiceMemoDetail` records

### Managing Approvals
```
Create request → Status = PENDING_APPROVAL
Admin reviews → approveXxx() or rejectXxx()
System updates related records on approval
```

## Security Notes

### Current Configuration (Development)
- `CORS_ORIGIN_ALLOW_ALL = True` (too permissive)
- `ALLOWED_HOSTS = ["*"]` (too permissive)
- `DEBUG = True`

### Production Requirements
1. Set `DEBUG = False`
2. Restrict `ALLOWED_HOSTS` to specific domains
3. Set `CORS_ORIGIN_ALLOW_ALL = False`
4. Use secure credential management (not .env)
5. Configure HTTPS (SECURE_SSL_REDIRECT = True)
6. Set up proper static file serving (nginx/Apache)

## Dependencies (requirements.txt)

### Core
- Django 5.0.1
- mysqlclient 2.2.4
- python-decouple 3.8

### PDF Generation
- reportlab 4.4.1
- xhtml2pdf 0.2.17
- Pillow 10.2.0

### QR Codes
- qrcode 7.4.2

### Other
- django-cors-headers 4.3.1
- requests 2.32.4
- cryptography 45.0.4

## Testing Notes

### Current State
- Empty test files in `core/tests.py` and `transactions/tests.py`
- No CI/CD setup

### For New Tests
- Use Django's built-in testing framework
- Test database auto-created with `test_` prefix
- Consider SQLite for faster test execution

## Git Workflow

### Branches
- `SIS` - Main branch (for PRs)
- `dev` - Development branch

### Commit Style
- Keep commits focused and descriptive
- Run linting before committing

Agent System
This project uses role-specific agents that activate based on task context. Claude will automatically assume the appropriate role based on the task being performed.
Agent Selection Rules
Developer Agent (/agents/dev.md)
Activates when:

Creating or modifying Python/Django code
Working with models, views, serializers, or URLs
Database migrations or schema changes
API development or integration
Performance optimization
Refactoring existing code

Tester Agent (/agents/tester.md)
Activates when:

Writing or running tests
Debugging failing tests
Test coverage analysis
Creating fixtures or factories
QA-related tasks
Validating functionality

UI/UX Agent (/agents/ui-ux.md)
Activates when:

Working with templates (HTML/Jinja2)
CSS/SCSS styling
JavaScript/frontend code
Form design and validation UX
Accessibility improvements
User flow optimization