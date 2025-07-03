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
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (True/False)
- `DB_NAME`: MySQL database name
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host
- `DB_PORT`: Database port
- `PROD_URL`: Production URL for QR codes
- `QR_METHOD_NAME`: QR code scanning method

### Database
- **Engine**: MySQL (configured in settings.py)
- **Tables**: Prefixed with `dc_` (daycare)
- **Timezone**: Asia/Colombo

### Static Files
- **CSS**: Bootstrap + custom styles in `static/assets/css/`
- **JavaScript**: jQuery + DataTables in `static/assets/js/`
- **Images**: Stored in `media/child_images/`
- **QR Codes**: Generated in `media/qr/`

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
- Short session timeout (3 minutes)
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