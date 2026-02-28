"""Local multi-step form application for end-to-end testing.

Run with:
    conda activate ui_agent
    pip install flask   # if not installed
    python test_server/app.py

Then point the agent at http://localhost:5555/form
"""

from __future__ import annotations

from flask import Flask, render_template_string, request, redirect, url_for, session
from markupsafe import Markup
import os

app = Flask(__name__)
app.secret_key = "ui-agent-test-secret-key"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f7fa; color: #333; }
  .container { max-width: 640px; margin: 40px auto; background: #fff;
               border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
               padding: 32px; }
  h1 { font-size: 1.5rem; margin-bottom: 8px; }
  .step-indicator { color: #666; font-size: 0.9rem; margin-bottom: 24px; }
  .progress { display: flex; gap: 8px; margin-bottom: 24px; }
  .progress .dot { width: 12px; height: 12px; border-radius: 50%;
                   background: #ddd; }
  .progress .dot.active { background: #4a90d9; }
  .progress .dot.done { background: #5cb85c; }
  .form-group { margin-bottom: 16px; }
  label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 0.9rem; }
  input, select { width: 100%; padding: 10px 12px; border: 1px solid #ccc;
                  border-radius: 4px; font-size: 1rem; }
  input:focus, select:focus { outline: none; border-color: #4a90d9;
                               box-shadow: 0 0 0 2px rgba(74,144,217,0.2); }
  .error-message { color: #d9534f; font-size: 0.85rem; margin-top: 4px; display: none; }
  .error-message.visible { display: block; }
  .btn { display: inline-block; padding: 10px 24px; border: none; border-radius: 4px;
         font-size: 1rem; cursor: pointer; text-decoration: none; }
  .btn-primary { background: #4a90d9; color: #fff; }
  .btn-primary:hover { background: #3a7bc8; }
  .btn-secondary { background: #e0e0e0; color: #333; }
  .btn-secondary:hover { background: #d0d0d0; }
  .btn-row { display: flex; justify-content: space-between; margin-top: 24px; }
  .confirmation { background: #dff0d8; border: 1px solid #d6e9c6;
                  border-radius: 4px; padding: 16px; margin-bottom: 16px; }
  .confirmation h2 { color: #3c763d; font-size: 1.2rem; margin-bottom: 8px; }
  .summary-table { width: 100%; border-collapse: collapse; }
  .summary-table td { padding: 8px 12px; border-bottom: 1px solid #eee; }
  .summary-table td:first-child { font-weight: 600; width: 40%; color: #555; }
  .required::after { content: " *"; color: #d9534f; }
</style>
</head>
<body>
<div class="container">
  {{ content|safe }}
</div>
</body>
</html>
"""

STEP1_CONTENT = """
<h1>Insurance Application</h1>
<div class="step-indicator" data-testid="step-indicator">Step 1 of 3 — Personal Information</div>
<div class="progress">
  <div class="dot active"></div>
  <div class="dot"></div>
  <div class="dot"></div>
</div>
<form method="POST" action="/form/step1" id="step1-form">
  <div class="form-group">
    <label for="first_name" class="required">First Name</label>
    <input type="text" id="first_name" name="first_name" required
           placeholder="Enter your first name"
           value="{{ data.get('first_name', '') }}">
    <div class="error-message" id="first_name-error">First name is required</div>
  </div>
  <div class="form-group">
    <label for="last_name" class="required">Last Name</label>
    <input type="text" id="last_name" name="last_name" required
           placeholder="Enter your last name"
           value="{{ data.get('last_name', '') }}">
    <div class="error-message" id="last_name-error">Last name is required</div>
  </div>
  <div class="form-group">
    <label for="email" class="required">Email Address</label>
    <input type="email" id="email" name="email" required
           placeholder="you@example.com"
           value="{{ data.get('email', '') }}">
    <div class="error-message" id="email-error">Valid email is required</div>
  </div>
  <div class="form-group">
    <label for="phone">Phone Number</label>
    <input type="tel" id="phone" name="phone"
           placeholder="555-123-4567"
           value="{{ data.get('phone', '') }}">
  </div>
  <div class="form-group">
    <label for="date_of_birth" class="required">Date of Birth</label>
    <input type="text" id="date_of_birth" name="date_of_birth" required
           placeholder="MM/DD/YYYY"
           value="{{ data.get('date_of_birth', '') }}">
    <div class="error-message" id="date_of_birth-error">Date of birth is required</div>
  </div>
  <div class="form-group">
    <label for="gender" class="required">Gender</label>
    <select id="gender" name="gender" required>
      <option value="">-- Select --</option>
      <option value="Male" {{ 'selected' if data.get('gender') == 'Male' }}>Male</option>
      <option value="Female" {{ 'selected' if data.get('gender') == 'Female' }}>Female</option>
      <option value="Other" {{ 'selected' if data.get('gender') == 'Other' }}>Other</option>
    </select>
    <div class="error-message" id="gender-error">Gender is required</div>
  </div>
  <div class="btn-row">
    <span></span>
    <button type="submit" class="btn btn-primary" data-testid="next-button">Next Step</button>
  </div>
</form>
"""

STEP2_CONTENT = """
<h1>Insurance Application</h1>
<div class="step-indicator" data-testid="step-indicator">Step 2 of 3 — Address Information</div>
<div class="progress">
  <div class="dot done"></div>
  <div class="dot active"></div>
  <div class="dot"></div>
</div>
<form method="POST" action="/form/step2" id="step2-form">
  <div class="form-group">
    <label for="address" class="required">Street Address</label>
    <input type="text" id="address" name="address" required
           placeholder="123 Main Street"
           value="{{ data.get('address', '') }}">
    <div class="error-message" id="address-error">Street address is required</div>
  </div>
  <div class="form-group">
    <label for="city" class="required">City</label>
    <input type="text" id="city" name="city" required
           placeholder="Springfield"
           value="{{ data.get('city', '') }}">
    <div class="error-message" id="city-error">City is required</div>
  </div>
  <div class="form-group">
    <label for="state" class="required">State</label>
    <select id="state" name="state" required>
      <option value="">-- Select State --</option>
      <option value="Alabama">Alabama</option>
      <option value="Alaska">Alaska</option>
      <option value="Arizona">Arizona</option>
      <option value="California">California</option>
      <option value="Colorado">Colorado</option>
      <option value="Florida">Florida</option>
      <option value="Georgia">Georgia</option>
      <option value="Illinois">Illinois</option>
      <option value="New York">New York</option>
      <option value="Oregon">Oregon</option>
      <option value="Texas">Texas</option>
      <option value="Washington">Washington</option>
    </select>
    <div class="error-message" id="state-error">State is required</div>
  </div>
  <div class="form-group">
    <label for="zip_code" class="required">ZIP Code</label>
    <input type="text" id="zip_code" name="zip_code" required
           placeholder="12345"
           value="{{ data.get('zip_code', '') }}">
    <div class="error-message" id="zip_code-error">ZIP code is required</div>
  </div>
  <div class="btn-row">
    <a href="/form/step1" class="btn btn-secondary" data-testid="back-button">Back</a>
    <button type="submit" class="btn btn-primary" data-testid="next-button">Next Step</button>
  </div>
</form>
"""

STEP3_CONTENT = """
<h1>Insurance Application</h1>
<div class="step-indicator" data-testid="step-indicator">Step 3 of 3 — Coverage Details</div>
<div class="progress">
  <div class="dot done"></div>
  <div class="dot done"></div>
  <div class="dot active"></div>
</div>
<form method="POST" action="/form/step3" id="step3-form">
  <div class="form-group">
    <label for="coverage_type" class="required">Coverage Type</label>
    <select id="coverage_type" name="coverage_type" required>
      <option value="">-- Select --</option>
      <option value="Individual" {{ 'selected' if data.get('coverage_type') == 'Individual' }}>Individual</option>
      <option value="Family" {{ 'selected' if data.get('coverage_type') == 'Family' }}>Family</option>
      <option value="Group" {{ 'selected' if data.get('coverage_type') == 'Group' }}>Group</option>
    </select>
    <div class="error-message" id="coverage_type-error">Coverage type is required</div>
  </div>
  <div class="form-group">
    <label for="plan_type" class="required">Plan Type</label>
    <select id="plan_type" name="plan_type" required>
      <option value="">-- Select --</option>
      <option value="Bronze" {{ 'selected' if data.get('plan_type') == 'Bronze' }}>Bronze</option>
      <option value="Silver" {{ 'selected' if data.get('plan_type') == 'Silver' }}>Silver</option>
      <option value="Gold" {{ 'selected' if data.get('plan_type') == 'Gold' }}>Gold</option>
      <option value="Platinum" {{ 'selected' if data.get('plan_type') == 'Platinum' }}>Platinum</option>
    </select>
    <div class="error-message" id="plan_type-error">Plan type is required</div>
  </div>
  <div class="form-group">
    <label for="annual_income">Annual Income ($)</label>
    <input type="text" id="annual_income" name="annual_income"
           placeholder="e.g. 75000"
           value="{{ data.get('annual_income', '') }}">
  </div>
  <div class="form-group">
    <label for="tobacco_use" class="required">Tobacco Use</label>
    <select id="tobacco_use" name="tobacco_use" required>
      <option value="">-- Select --</option>
      <option value="Yes" {{ 'selected' if data.get('tobacco_use') == 'Yes' }}>Yes</option>
      <option value="No" {{ 'selected' if data.get('tobacco_use') == 'No' }}>No</option>
    </select>
    <div class="error-message" id="tobacco_use-error">Tobacco use selection is required</div>
  </div>
  <div class="btn-row">
    <a href="/form/step2" class="btn btn-secondary" data-testid="back-button">Back</a>
    <button type="submit" class="btn btn-primary" data-testid="submit-button">Submit Application</button>
  </div>
</form>
"""

CONFIRMATION_CONTENT = """
<h1>Insurance Application</h1>
<div class="step-indicator" data-testid="step-indicator">Application Submitted</div>
<div class="progress">
  <div class="dot done"></div>
  <div class="dot done"></div>
  <div class="dot done"></div>
</div>
<div class="confirmation" data-testid="confirmation-message">
  <h2>Application Submitted Successfully!</h2>
  <p>Your insurance application has been received. Your confirmation number is
     <strong data-testid="confirmation-number">CONF-{{ conf_number }}</strong>.</p>
</div>
<h3 style="margin-bottom: 12px;">Application Summary</h3>
<table class="summary-table" data-testid="summary-table">
  {% for label, value in summary %}
  <tr>
    <td>{{ label }}</td>
    <td>{{ value }}</td>
  </tr>
  {% endfor %}
</table>
<div class="btn-row" style="margin-top: 24px;">
  <a href="/form" class="btn btn-primary" data-testid="new-application-button">Start New Application</a>
</div>
"""

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

STEP1_REQUIRED = ["first_name", "last_name", "email", "date_of_birth", "gender"]
STEP2_REQUIRED = ["address", "city", "state", "zip_code"]
STEP3_REQUIRED = ["coverage_type", "plan_type", "tobacco_use"]

FIELD_LABELS = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email Address",
    "phone": "Phone Number",
    "date_of_birth": "Date of Birth",
    "gender": "Gender",
    "address": "Street Address",
    "city": "City",
    "state": "State",
    "zip_code": "ZIP Code",
    "coverage_type": "Coverage Type",
    "plan_type": "Plan Type",
    "annual_income": "Annual Income",
    "tobacco_use": "Tobacco Use",
}


def _validate_required(form_data: dict, required: list[str]) -> list[str]:
    errors = []
    for field in required:
        if not form_data.get(field, "").strip():
            errors.append(f"{FIELD_LABELS.get(field, field)} is required")
    return errors


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return redirect(url_for("form_step1"))


@app.route("/form")
@app.route("/form/step1", methods=["GET", "POST"])
def form_step1():
    if request.method == "POST":
        data = dict(request.form)
        errors = _validate_required(data, STEP1_REQUIRED)
        if errors:
            content = render_template_string(STEP1_CONTENT, data=data, errors=errors)
            # Show validation errors via JS injection
            error_script = "<script>"
            for field in STEP1_REQUIRED:
                if not data.get(field, "").strip():
                    error_script += (
                        f"document.getElementById('{field}-error')"
                        f".classList.add('visible');"
                    )
            error_script += "</script>"
            return render_template_string(
                LAYOUT, title="Step 1 — Personal Info", content=content + error_script
            )
        session["step1"] = data
        return redirect(url_for("form_step2"))

    data = session.get("step1", {})
    content = render_template_string(STEP1_CONTENT, data=data)
    return render_template_string(
        LAYOUT, title="Step 1 — Personal Info", content=content
    )


@app.route("/form/step2", methods=["GET", "POST"])
def form_step2():
    if "step1" not in session:
        return redirect(url_for("form_step1"))

    if request.method == "POST":
        data = dict(request.form)
        errors = _validate_required(data, STEP2_REQUIRED)
        if errors:
            content = render_template_string(STEP2_CONTENT, data=data, errors=errors)
            error_script = "<script>"
            for field in STEP2_REQUIRED:
                if not data.get(field, "").strip():
                    error_script += (
                        f"document.getElementById('{field}-error')"
                        f".classList.add('visible');"
                    )
            error_script += "</script>"
            return render_template_string(
                LAYOUT, title="Step 2 — Address", content=content + error_script
            )
        session["step2"] = data
        return redirect(url_for("form_step3"))

    data = session.get("step2", {})
    content = render_template_string(STEP2_CONTENT, data=data)
    return render_template_string(LAYOUT, title="Step 2 — Address", content=content)


@app.route("/form/step3", methods=["GET", "POST"])
def form_step3():
    if "step1" not in session or "step2" not in session:
        return redirect(url_for("form_step1"))

    if request.method == "POST":
        data = dict(request.form)
        errors = _validate_required(data, STEP3_REQUIRED)
        if errors:
            content = render_template_string(STEP3_CONTENT, data=data, errors=errors)
            error_script = "<script>"
            for field in STEP3_REQUIRED:
                if not data.get(field, "").strip():
                    error_script += (
                        f"document.getElementById('{field}-error')"
                        f".classList.add('visible');"
                    )
            error_script += "</script>"
            return render_template_string(
                LAYOUT, title="Step 3 — Coverage", content=content + error_script
            )
        session["step3"] = data
        return redirect(url_for("form_confirmation"))

    data = session.get("step3", {})
    content = render_template_string(STEP3_CONTENT, data=data)
    return render_template_string(LAYOUT, title="Step 3 — Coverage", content=content)


@app.route("/form/confirmation")
def form_confirmation():
    if not all(k in session for k in ("step1", "step2", "step3")):
        return redirect(url_for("form_step1"))

    all_data = {**session["step1"], **session["step2"], **session["step3"]}
    import hashlib, time as _t

    conf_number = hashlib.md5(f"{_t.time()}{all_data}".encode()).hexdigest()[:8].upper()

    summary = [(FIELD_LABELS.get(k, k), v) for k, v in all_data.items() if v]

    content = render_template_string(
        CONFIRMATION_CONTENT, conf_number=conf_number, summary=summary
    )
    # Clear session for next test run
    session.clear()
    return render_template_string(
        LAYOUT, title="Application Confirmed", content=content
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  Multi-Step Form Test Server")
    print("  URL: http://localhost:5555/form")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5555, debug=False)
