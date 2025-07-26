# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based **Daycare Management System** called "PolymathDayCare" that handles:
- Child enrollment and management
- Package pricing and billing
- Attendance tracking via QR codes
- Invoice memo generation
- Holiday and rate management
- Branch and center management

## Development Commands

### Running the Application
```bash
# Activate virtual environment (if using venv)
source env/bin/activate  # On Windows: env\Scripts\activate

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

# Run with verbosity for detailed output
python manage.py test --verbosity=2

# Run specific test class or method
python manage.py test core.tests.SomeTestClass
python manage.py test core.tests.SomeTestClass.test_method

# Keep test database after tests (faster subsequent runs)
python manage.py test --keepdb

# Run tests in parallel
python manage.py test --parallel
```

### Code Quality & Linting
```bash
# Note: Linting tools need to be installed first
# pip install ruff mypy black isort

# Format code with Ruff (configured in VS Code)
ruff format .

# Lint and auto-fix issues
ruff check . --fix

# Check without fixing
ruff check .

# Type checking (if mypy installed)
mypy core/ transactions/

# Security linting (if bandit installed)
bandit -r core/ transactions/
```

## Architecture Overview

### Core Applications
- **core/**: Main application containing all business logic
- **transactions/**: Currently empty but intended for financial transactions
- **daycareSystem/**: Django project settings and configuration

### Database Models (core/models.py)
Key models in hierarchical order:

**Base Infrastructure:**
- `BaseClass`: Abstract base with common fields (id, dates, user tracking, is_active)
- `Branch`: Physical locations
- `DayCare`: Centers within branches
- `PackageType`: Normal vs Holiday packages
- `PackageTerm`: Fixed vs Dynamic packages

**Child Management:**
- `Child`: Core child information with QR codes
- `ChildEnrollment`: Enrollment process with approval workflow
- `ChildPackageMapping`: Links children to their packages with effective dates

**Package & Pricing:**
- `FixedPackage`: Time-based packages with fixed hours
- `FlexPackages`: Flexible hour packages
- `ExtraHoursAfter530`: Extra charges after 5:30 PM
- `ExtraHoursUpTo530`: Extra charges until 5:30 PM
- `Discount`: Discount codes with approval workflow

**Attendance & Billing:**
- `AttendanceLog`: QR code-based attendance tracking
- `InvoiceMemo`: Main invoice with summary totals
- `InvoiceMemoDetail`: Detailed monthly breakdown (3 records per memo)
- `PaymentTransaction`: Payment records

**Workflow Management:**
- `PackageChangerequest`: Package change approvals
- `CenterChangerequest`: Center transfer requests
- `Holiday`: Holiday management with automatic day calculations

### URL Structure (core/urls.py)
Major URL patterns:
- `/`: Home dashboard
- `/child/`: Child management
- `/enrollments/`: Enrollment management
- `/packages/`: Package configuration
- `/attendance/`: Attendance tracking
- `/memo_data_entry/`: Invoice generation
- `/reports/`: Various reports

### Template Structure
- `templates/base.html`: Main layout
- `templates/partials/`: Reusable form components
- `templates/reports/`: Report templates
- `templates/utils/`: Data import utilities

## Configuration

### Environment Variables (.env)
Required variables:
- `SECRET_KEY`: Django secret key for cryptographic signing
- `DEBUG`: Debug mode (True/False)
- `DB_NAME`: MySQL database name (default: polymath_core)
- `DB_USER`: Database username (default: root)
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host (default: localhost)
- `DB_PORT`: Database port (default: 3306)
- `PROD_URL`: Production URL for QR codes (default: https://dc.polymathcore.online/)
- `QR_METHOD_NAME`: QR code scanning method (default: checkInView)

**Security Note**: Environment file contains actual credentials. For production, use secure credential management.

### Database
- **Engine**: MySQL via `django.db.backends.mysql`
- **Driver**: mysqlclient 2.2.4
- **Tables**: Prefixed with `dc_` (daycare)
- **Timezone**: Asia/Colombo (overrides UTC)
- **Connection**: All parameters from environment variables

### Static Files
- **CSS**: Bootstrap + custom styles in `static/assets/css/`
- **JavaScript**: jQuery + DataTables in `static/assets/js/`
- **Images**: Stored in `media/child_images/`
- **QR Codes**: Generated in `media/qr/`
- **Static URL**: `/static/` (development), collected to `staticfiles/` (production)
- **Media URL**: `media/` with auto-created directories

### Code Quality Setup
**Current VS Code Configuration**:
- Ruff configured as default Python formatter (87-88 character line limit)
- Format on save and auto-organize imports enabled
- Django template linting disabled

**Missing Dependencies** (need to install):
```bash
pip install ruff mypy black isort pre-commit bandit
```

**Recommended Configuration Files**:
- `pyproject.toml`: Ruff/Black configuration
- `.pre-commit-config.yaml`: Pre-commit hooks
- `mypy.ini`: Type checking configuration

## Key Features

### Approval Workflows
Many models use a 3-state approval system:
- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`

### QR Code System
- Each child gets a unique QR code
- QR codes link to attendance recording
- Images stored in `media/qr/`

### Invoice System
**New architecture** (replace old system):
- `InvoiceMemo`: Summary with totals
- `InvoiceMemoDetail`: Monthly breakdown (Outstanding, Previous, Current)
- Each memo has exactly 3 detail records

### Package System
- **Fixed Packages**: Time-based with automatic hour calculation
- **Flex Packages**: Hour-based flexible pricing
- **Holiday Packages**: Special pricing for holidays
- **Extra Hours**: Two tiers (before/after 5:30 PM)

## Development Notes

### Model Relationships
- Most models extend `BaseClass` for consistent auditing
- Foreign keys use CASCADE deletion (be careful)
- Many-to-many relationships handled through explicit mapping models

### Sessions
- Session timeout: 50 minutes (3000 seconds)
- Sessions extend on each request (`SESSION_SAVE_EVERY_REQUEST = True`)
- Sessions expire on browser close
- Login required for most views

### File Uploads
- Child images: `media/child_images/`
- Enrollment forms: `media/enrollment_forms/`
- QR codes: `media/qr/`

### Important Constraints
- Unique constraints on package mappings
- Date range validations on effective periods
- Attendance logging limited to one per child per day

## Common Tasks

### Adding New Package Types
1. Create in `PackageType` model
2. Configure in `FixedPackage` or `FlexPackages`
3. Set up extra hours mapping in `PackageExtraHoursMapping`

### Generating Invoices
1. Use memo data entry interface
2. System auto-calculates based on attendance
3. Creates `InvoiceMemo` with 3 `InvoiceMemoDetail` records

### Managing Approvals
Most approval workflows follow the pattern:
- Create request with `PENDING_APPROVAL`
- Admin approves/rejects
- System updates related records on approval

### QR Code Generation
- Automatically generated on child creation
- Links to attendance recording URL
- Format: `{PROD_URL}/{QR_METHOD_NAME}/{admission_number}/`

## Security & Production Notes

### Current Security Configuration
- **CORS**: Very permissive (`CORS_ORIGIN_ALLOW_ALL = True`)
- **Allowed Hosts**: Mixed configuration (both restrictive and `["*"]`)
- **CSRF**: Trusted origins limited to `polymathcore.online` domain
- **Sessions**: Server-side with automatic expiration

### Production Considerations
**Before Deployment**:
1. **Environment Security**: Remove actual credentials from `.env`, use secure credential management
2. **CORS Configuration**: Restrict `CORS_ORIGIN_ALLOW_ALL` to specific domains
3. **Host Configuration**: Remove permissive `ALLOWED_HOSTS = ["*"]`
4. **Debug Mode**: Ensure `DEBUG=False` in production
5. **Static File Serving**: Configure web server (nginx/Apache) for static files

**Dependencies with Security Implications**:
- `mysqlclient`: Direct database access - secure connection strings
- `django-cors-headers`: Currently very permissive
- `reportlab` + `xhtml2pdf`: PDF generation - validate input data

### Testing Notes
**Current State**: 
- Empty test files in `core/tests.py` and `transactions/tests.py`
- No test database configuration (uses Django defaults)
- No continuous integration setup

**For New Tests**:
- Django's built-in testing framework available
- Test database auto-created with `test_` prefix
- Consider using SQLite for faster test execution