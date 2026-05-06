"""
_bdjobs_registry.py - BDJobs Job Registry for Olympic Industries PLC.
"""

BDJOBS_JOB_REGISTRY = {

    # ── IT DEPARTMENT (AI & Digital Transformation + ICT) ─────────────────────

    "AIDigital_Transformation-Executive": {
        "job_title":         "Executive / Sr. Executive - AI & Digital Transformation",
        "department":        "AI & Digital Transformation",
        "location":          "Dhaka",
        "deadline":          "15 Mar 2026",
        "experience":        "1 to 4 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 35,000 – 65,000/month",
        "education_req":     "Bachelor's (BSc CSE preferred; relaxed for strong portfolio)",
        "min_experience":    "1 year",
        "required_skills": [
            "Python", "Machine Learning", "Computer Vision", "OpenCV",
            "Object Detection", "Deep Learning", "NumPy", "Pandas",
            "SQL", "System Troubleshooting",
        ],
        "bonus_skills": [
            "FastAPI", "Docker", "Edge Computing", "Camera Integration",
            "MLOps", "Industrial Automation", "Dashboard Development",
        ],
        "red_flags": [
            "No deployed ML/AI project",
            "Theoretical only — no production code",
            "No Python proficiency",
        ],
        "scoring_note": (
            "Key role: design/deploy AI & Machine Vision for factory automation. "
            "Computer Vision (detection, tracking, counting) is the PRIMARY skill. "
            "Portfolio of deployed industrial AI projects is mandatory for Shortlist. "
            "Candidates from BSc CSE with proven projects score equal to or higher than "
            "MSc without portfolio. Education requirement is explicitly relaxed for strong candidates."
        ),
        "weight_skills": 60, "weight_exp": 20, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "ICT-Executive": {
        "job_title":         "Executive - ICT",
        "department":        "Information & Communication Technology (ICT)",
        "location":          "Dhaka",
        "deadline":          "15 Mar 2026",
        "experience":        "2 to 4 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 35,000 – 60,000/month",
        "education_req":     "BSc in CSE from reputed institution",
        "min_experience":    "2 years",
        "required_skills": [
            "TCP/IP", "OSPF", "VLAN", "EIGRP", "DNS", "DHCP", "NAT",
            "Switching & Routing", "IPT System", "CCTV", "Microsoft Hyper-V",
            "Virtual Desktop", "Odoo ERP", "Python", "JavaScript", "Java",
            "JSON", "REST API", "GitHub", "CPanel",
        ],
        "bonus_skills": [
            "VMware", "PostgreSQL", "MySQL", "Network Security", "Firewall",
            "LAN/WAN Administration", "VPN", "Project Management Software",
        ],
        "red_flags": [
            "No TCP/IP / networking knowledge",
            "No ERP support experience",
            "No scripting or development ability",
        ],
        "scoring_note": (
            "Dual role: networking (LAN/WAN/firewall/VPN) AND ERP/software support. "
            "Both domains must be present. Hyper-V and virtualization experience is "
            "explicitly required. Willingness to travel to factories is mandatory."
        ),
        "weight_skills": 55, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 0, "weight_culture": 5,
    },

    # ── SECURITY DEPARTMENT ────────────────────────────────────────────────────

    "Security-Officer": {
        "job_title":         "Security Officer",
        "department":        "Security",
        "location":          "Narayanganj",
        "deadline":          "15 Mar 2026",
        "experience":        "5 to 8 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 50,000/month",
        "education_req":     "Bachelor's degree (any discipline)",
        "min_experience":    "5 years",
        "required_skills": [
            "Access Control Systems", "Fire Safety & Alarm Systems",
            "Incident Reporting & Documentation", "Security Equipment Handling",
            "Risk Assessment & Mitigation", "CCTV Surveillance",
            "Guard Management", "Factory Security Operations",
            "Compliance Audit Support (ISO/HACCP/BSCI/SEDEX/WRAP)",
        ],
        "bonus_skills": [
            "Ex-Defense / Military Background",
            "Fire Safety Certification",
            "ISO Compliance Knowledge",
        ],
        "red_flags": [
            "No physical security / factory security experience",
            "No experience managing guard teams",
            "No knowledge of access control systems",
        ],
        "scoring_note": (
            "Supervisory role: manages all security personnel and gate operations 24/7. "
            "Ex-Defense background is explicitly preferred — should receive +10 bonus on "
            "culture_fit_score. Compliance audit support (ISO, HACCP, BSCI, SEDEX, WRAP) "
            "is a key differentiator over pure security roles. "
            "Factory/manufacturing security experience is required; mall/banking security alone is insufficient."
        ),
        "weight_skills": 40, "weight_exp": 40, "weight_edu": 5,
        "weight_leadership": 10, "weight_culture": 5,
    },

    "Security-InCharge": {
        "job_title":         "Security In-Charge",
        "department":        "Security",
        "location":          "Narayanganj",
        "deadline":          "15 Mar 2026",
        "experience":        "3 to 5 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 20,000 – 35,000/month",
        "education_req":     "Minimum HSC / Bachelor preferred",
        "min_experience":    "3 years",
        "required_skills": [
            "Access Control Systems", "Fire Safety & Alarm Systems",
            "Incident Reporting & Documentation", "Security Equipment Handling",
            "Risk Assessment", "Leadership of Security Personnel",
            "Patrol Management", "Visitor/Vehicle Access Control",
        ],
        "bonus_skills": [
            "Ex-Defense / Military Background",
            "Emergency Response Training",
        ],
        "red_flags": [
            "No team supervision experience",
            "No access control or surveillance knowledge",
        ],
        "scoring_note": (
            "Shift supervisor role — manages security during assigned shift. "
            "Ex-Defense background strongly preferred. Education requirement is HSC minimum "
            "so degree level should not heavily penalize HSC holders. "
            "Leadership evidence (managing 3-10 guards) is critical for Shortlist."
        ),
        "weight_skills": 35, "weight_exp": 40, "weight_edu": 5,
        "weight_leadership": 15, "weight_culture": 5,
    },

    # ── FINANCE AND ACCOUNTS ───────────────────────────────────────────────────

    "Accounts-Fund-Executive": {
        "job_title":         "Executive - Accounts (Fund)",
        "department":        "Finance and Accounts",
        "location":          "Dhaka",
        "deadline":          "25 Apr 2026",
        "experience":        "At least 1 year (Freshers encouraged)",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Bachelor/Master in Accounting or Finance; CA (CC) preferred",
        "min_experience":    "Any",
        "required_skills": [
            "WPPF Management", "Provident Fund (PF) Management",
            "Gratuity Fund Management", "Final Settlement Processing",
            "Labor Law Compliance", "Trustee Meeting Coordination",
            "Fund Documentation", "Microsoft Excel",
        ],
        "bonus_skills": [
            "CA (CC) Qualification", "ERP Experience",
            "Public University Background", "Bangladesh Labor Act Knowledge",
        ],
        "red_flags": [
            "No fund management exposure",
            "No Excel proficiency",
        ],
        "scoring_note": (
            "Specialist role managing employee benefit funds (WPPF, PF, Gratuity). "
            "Practical PF/WPPF experience is explicitly preferred. "
            "Freshers from reputed universities with CA (CC) are acceptable. "
            "Public university graduates receive preference — note in edu_tier scoring."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 20,
        "weight_leadership": 0, "weight_culture": 10,
    },

    "Accounts-Billing-SrExecutive": {
        "job_title":         "Sr. Executive - Accounts (Billing)",
        "department":        "Finance and Accounts",
        "location":          "Dhaka",
        "deadline":          "26 Apr 2026",
        "experience":        "At least 2 years (post CA CC)",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 35,000 – 60,000/month",
        "education_req":     "Bachelor/Master in Accounting or Finance; CA (CC) required",
        "min_experience":    "2 years",
        "required_skills": [
            "Billing Processing", "Tax & VAT Compliance",
            "Customer Account Reconciliation", "Bill Verification",
            "Billing Report Preparation", "ERP/Accounting Software",
            "MS Excel", "Documentation",
        ],
        "bonus_skills": [
            "SAP FICO", "CA (CC) Post-Qualification",
            "Bangladesh Tax Law", "Public University Background",
        ],
        "red_flags": [
            "No CA (CC) qualification",
            "No VAT/Tax experience",
            "No billing or accounts receivable experience",
        ],
        "scoring_note": (
            "CA (CC) is explicitly required — candidates without it should be flagged. "
            "2 years post-CA (CC) experience is mandatory. "
            "Tax and VAT compliance during billing is a core duty."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 25,
        "weight_leadership": 0, "weight_culture": 5,
    },

    "CostControl-SrExecutive": {
        "job_title":         "Sr. Executive / Asst. Manager - Cost Control & Budgeting",
        "department":        "Finance and Accounts",
        "location":          "Dhaka",
        "deadline":          "12 Oct 2025",
        "experience":        "3 to 6 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 45,000 – 80,000/month",
        "education_req":     "Bachelor/Master in Accounting; CA.CC Certificate Level",
        "min_experience":    "3 years",
        "required_skills": [
            "Cost Sheet Preparation & Analysis", "Budget Preparation",
            "Cost Forecasting", "Profitability Reporting",
            "Pricing Support", "Tax Knowledge", "VAT Knowledge", "ERP Software",
            "Financial Analysis", "MS Office",
        ],
        "bonus_skills": [
            "CA (CC)", "FMCG Costing Experience", "SAP FICO",
            "Standard Costing", "Variance Analysis",
        ],
        "red_flags": [
            "No costing or budgeting experience",
            "No Tax/VAT knowledge",
            "No ERP experience",
        ],
        "scoring_note": (
            "Cost accounting specialty role — not generic finance. "
            "Monthly/quarterly costing and profitability reports are core deliverables. "
            "Sound knowledge of Tax, VAT, and ERP is explicitly required."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 20,
        "weight_leadership": 5, "weight_culture": 5,
    },

    # ── INTERNAL AUDIT ─────────────────────────────────────────────────────────

    "InternalAudit-ExecutiveSr": {
        "job_title":         "Executive / Sr. Executive - Internal Audit",
        "department":        "Internal Audit",
        "location":          "Dhaka",
        "deadline":          "10 Mar 2025",
        "experience":        "2 to 4 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 35,000 – 65,000/month",
        "education_req":     "MBA Accounting & Finance / M.Com with CA (CC)",
        "min_experience":    "2 years",
        "required_skills": [
            "Internal Audit Execution", "Audit Report Preparation",
            "Financial Document Review", "Compliance Audit",
            "Operational Audit", "Process Audit", "Physical Inventory Audit",
            "ERP Knowledge", "MS Office", "VAT Knowledge", "Withholding Tax",
        ],
        "bonus_skills": [
            "Pre-Audit Experience (Party Payment/Bill Voucher)",
            "FMCG Company Audit Experience", "CA (CC) / ACCA",
            "Cost Audit", "Investigation", "Surprise Audit",
        ],
        "red_flags": [
            "No FMCG audit experience",
            "No ERP knowledge",
            "No VAT/Withholding Tax knowledge",
        ],
        "scoring_note": (
            "FMCG company audit experience is explicitly prioritized. "
            "Pre-audit experience (party payment, bill voucher, advances) gets high priority. "
            "Both operational and financial audit coverage is expected."
        ),
        "weight_skills": 40, "weight_exp": 35, "weight_edu": 15,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "InternalAudit-AsstManager": {
        "job_title":         "Asst. Manager / Sr. Executive - Internal Audit",
        "department":        "Internal Audit",
        "location":          "Dhaka",
        "deadline":          "07 Nov 2025",
        "experience":        "2 to 4 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 50,000 – 90,000/month",
        "education_req":     "MBA Accounting / CACC (flexible for experienced)",
        "min_experience":    "2 years",
        "required_skills": [
            "Audit Program Development", "Internal Control Design",
            "Audit Report Writing (Monthly/Quarterly/Annual)", "Cost Audit",
            "Pre-Audit", "Surprise Audit", "Investigation", "Process Audit",
            "Physical Inventory Audit", "Financial Analysis Techniques",
            "ERP", "MS Office", "VAT", "Withholding Tax",
        ],
        "bonus_skills": [
            "CIA (Certified Internal Auditor)", "ACCA",
            "FMCG Senior Audit Management", "Big 4 / CA Firm Experience",
        ],
        "red_flags": [
            "No audit program design experience",
            "Only junior execution without supervisory exposure",
        ],
        "scoring_note": (
            "Senior role: develops audit programs and guides junior auditors. "
            "FMCG pre-audit experience is the top differentiator — state explicitly in scoring."
        ),
        "weight_skills": 35, "weight_exp": 35, "weight_edu": 15,
        "weight_leadership": 10, "weight_culture": 5,
    },

    # ── HUMAN RESOURCE ─────────────────────────────────────────────────────────

    "HR-JuniorOfficer": {
        "job_title":         "Junior Officer - HR",
        "department":        "Human Resource (HR)",
        "location":          "Narayanganj",
        "deadline":          "31 Jan 2026",
        "experience":        "2 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 20,000 – 35,000/month",
        "education_req":     "BBA/MBA in HRM",
        "min_experience":    "2 years",
        "required_skills": [
            "Bangladesh Labour Act & Labour Rules", "HR Software",
            "Microsoft Office Suite", "Recruitment & Selection",
            "Payroll & HRIS Management", "Employee Record Keeping",
            "Grievance Handling", "Training Administration",
            "Disciplinary Action Management",
        ],
        "bonus_skills": [
            "Factory HR Experience", "FMCG HR Experience",
            "ERP/SAP HR Module",
        ],
        "red_flags": [
            "No knowledge of Bangladesh Labour Act",
            "No payroll experience",
        ],
        "scoring_note": (
            "Factory-based HR role in Narayanganj. Bangladesh Labour Act 2006 knowledge "
            "is mandatory. FMCG/factory HR experience is preferred over corporate-only HR."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 20,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "HR-OfficerSr": {
        "job_title":         "Officer / Sr. Officer - HR",
        "department":        "Human Resource (HR)",
        "location":          "Narayanganj",
        "deadline":          "10 Jun 2025",
        "experience":        "2 to 5 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Any (FMCG Manufacturing experience required)",
        "min_experience":    "2 years",
        "required_skills": [
            "Bangladesh Labour Act", "HR Software", "Microsoft Office",
            "Performance Management System (PMS)", "Manpower Supply Planning",
            "Payroll Timelines", "Employee Orientation",
            "Training Plan Execution", "ERP",
        ],
        "bonus_skills": [
            "Factory HR", "FMCG HR", "Data Organization / HRIS",
        ],
        "red_flags": [
            "No Bangladesh Labour Act knowledge",
            "No PMS experience",
        ],
        "scoring_note": (
            "Narayanganj factory HR role. Performance management and timely payroll "
            "are the primary KPIs. Strong data organization skills explicitly stated."
        ),
        "weight_skills": 40, "weight_exp": 35, "weight_edu": 15,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "HR-ExecutiveSr": {
        "job_title":         "Executive / Sr. Executive - HR",
        "department":        "Human Resource (HR)",
        "location":          "Dhaka",
        "deadline":          "31 Aug 2025",
        "experience":        "Not specified (FMCG experience preferred)",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 55,000/month",
        "education_req":     "Not specified",
        "min_experience":    "Any",
        "required_skills": [
            "Bangladesh Labour Act", "ERP/HR Software", "Microsoft Office",
            "Performance Management System", "Recruitment & Onboarding",
            "Payroll Processing", "KPI & Target Setting",
            "Final Settlement Processing", "Change Management",
            "HR Policy Communication",
        ],
        "bonus_skills": [
            "FMCG Corporate HR", "Organizational Development",
            "SAP HR Module",
        ],
        "red_flags": [
            "No Bangladesh Labour Act knowledge",
            "No payroll processing experience",
        ],
        "scoring_note": (
            "Dhaka-based corporate HR with broader scope including change management "
            "and KPI setting. More strategic than factory HR roles. "
            "Final settlement processing and performance appraisal management are core KPIs."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 10, "weight_culture": 5,
    },

    # ── ADMIN DEPARTMENT ───────────────────────────────────────────────────────

    "Admin-Officer": {
        "job_title":         "Officer - Admin",
        "department":        "Admin",
        "location":          "Narayanganj",
        "deadline":          "28 Feb 2025",
        "experience":        "3 to 6 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Masters/Bachelor in any discipline",
        "min_experience":    "3 years",
        "required_skills": [
            "Regulatory Compliance Management", "Government Liaison",
            "REB/Titas/DIFE/Labor Office Documentation",
            "RAJUK/Upazilla Authority Coordination",
            "Fire Service NOC", "Vehicle Renewals & Insurance",
            "Factory Administration", "Vendor Management",
        ],
        "bonus_skills": [
            "Factory Administration Experience",
            "Utility Management (Gas/Power)",
            "Legal Documentation",
        ],
        "red_flags": [
            "No factory administration experience",
            "No government liaison experience",
        ],
        "scoring_note": (
            "Factory admin role focused on regulatory compliance and government liaison. "
            "Experience with RAJUK, DIFE, Labor Office, REB, Titas is explicitly required. "
            "Pure corporate/office admin experience without factory context is insufficient."
        ),
        "weight_skills": 40, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 10, "weight_culture": 5,
    },

    "Admin-OfficerSr-Construction": {
        "job_title":         "Officer / Sr. Officer - Admin (Construction)",
        "department":        "Admin",
        "location":          "Narayanganj",
        "deadline":          "31 Jan 2026",
        "experience":        "5 to 7 years (Construction/Real Estate)",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 35,000 – 55,000/month",
        "education_req":     "Masters/Bachelor in Business Administration",
        "min_experience":    "5 years",
        "required_skills": [
            "Construction/Real Estate Admin", "Document Management",
            "Subcontractor Coordination", "Construction Progress Tracking",
            "Legal & Regulatory Compliance", "Vendor Management",
            "Indent Raising",
        ],
        "bonus_skills": [
            "AutoCAD Basics", "Project Management",
            "Property Management",
        ],
        "red_flags": [
            "No construction or real estate experience",
            "Only general office admin",
        ],
        "scoring_note": (
            "Specifically requires 5-7 years in Construction/Real Estate. "
            "This is NOT a general admin role. Candidates without construction context "
            "should be flagged and capped at 50 on experience_score."
        ),
        "weight_skills": 35, "weight_exp": 40, "weight_edu": 10,
        "weight_leadership": 10, "weight_culture": 5,
    },

    "Admin-Manager": {
        "job_title":         "Manager - Admin",
        "department":        "Admin",
        "location":          "Narayanganj",
        "deadline":          "12 Oct 2025",
        "experience":        "8 to 10 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 80,000 – 140,000/month",
        "education_req":     "Minimum Graduation",
        "min_experience":    "8 years",
        "required_skills": [
            "Factory Safety Management", "Housekeeping & Pest Control",
            "Government/Regulatory Liaison", "License & Permit Renewal",
            "Canteen Management", "Contract Management (3rd Party)",
            "Vehicle Administration (Tax/Fitness/Insurance)",
            "Emergency Response Management",
        ],
        "bonus_skills": [
            "FMCG Factory Admin Management",
            "Fire Safety Certificate",
            "Labor Law Knowledge",
        ],
        "red_flags": [
            "No factory administration experience",
            "No government liaison history",
            "Less than 8 years total experience",
        ],
        "scoring_note": (
            "Senior factory admin manager. Health & safety, regulatory compliance, "
            "and third-party contract management are the key areas. "
            "Must show experience managing admin for large factory premises."
        ),
        "weight_skills": 35, "weight_exp": 40, "weight_edu": 10,
        "weight_leadership": 10, "weight_culture": 5,
    },

    # ── BRAND & MARKETING ─────────────────────────────────────────────────────

    "Brand-ExecutiveSr": {
        "job_title":         "Executive / Sr. Executive - Brand",
        "department":        "Brand & Marketing",
        "location":          "Dhaka",
        "deadline":          "20 Mar 2026",
        "experience":        "2 to 5 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 40,000 – 70,000/month",
        "education_req":     "BBA/MBA in Marketing",
        "min_experience":    "2 years",
        "required_skills": [
            "Brand Strategy Planning & Execution", "Campaign Management",
            "New Product Development", "Market & Consumer Analysis",
            "Product Performance Monitoring", "Microsoft Excel",
            "PowerPoint", "Data Analysis", "Customer Trend Analysis",
        ],
        "bonus_skills": [
            "FMCG Spice/Culinary/Snacks/Beverage Experience",
            "Digital Media Ideation", "Agency Negotiation",
            "Social Media Management",
        ],
        "red_flags": [
            "No FMCG brand experience",
            "No new product development involvement",
            "No data analysis capability",
        ],
        "scoring_note": (
            "Spice/Culinary/Snacks/Beverage FMCG experience is explicitly preferred. "
            "Brand strategy with data-driven execution and NPD are core requirements. "
            "Excel and PowerPoint proficiency are explicitly stated requirements."
        ),
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "Brand-SrExecutiveAsstManager": {
        "job_title":         "Sr. Executive / Asst. Manager - Brand",
        "department":        "Brand & Marketing",
        "location":          "Dhaka",
        "deadline":          "10 Jun 2025",
        "experience":        "3 to 7 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 55,000 – 100,000/month",
        "education_req":     "Not stated (FMCG food industry preferred)",
        "min_experience":    "3 years",
        "required_skills": [
            "Marketing Plan Preparation & Execution", "New Product Development",
            "Data Analysis for Trends & Insights", "Budget Management",
            "Social Media Brand Consistency", "Product Strategy Development",
            "Digital Media Execution", "Agency Coordination & Negotiation",
            "Competition Analysis",
        ],
        "bonus_skills": [
            "Core Brand Team FMCG Food Experience",
            "ATL/BTL Campaign Management",
            "Consumer Insight Research",
        ],
        "red_flags": [
            "No core brand team experience (3-4 years required)",
            "No digital media execution",
            "No agency management",
        ],
        "scoring_note": (
            "Senior brand role — 3-4 years in a Core Brand Team at a reputed FMCG food company "
            "is the benchmark for Shortlist. Budget management responsibility required. "
            "Innovation in digital and traditional media both expected."
        ),
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "Brand-GraphicDesigner": {
        "job_title":         "Graphic Designer",
        "department":        "Brand & Marketing",
        "location":          "Dhaka",
        "deadline":          "16 Dec 2025",
        "experience":        "1 to 2 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Bachelor's from any reputed institution",
        "min_experience":    "1 year",
        "required_skills": [
            "Adobe Illustrator", "Adobe Photoshop", "Adobe InDesign",
            "Packaging Design", "FMCG Shelf Impact Design",
            "Print-Ready File Preparation", "Brand-Aligned Visual Communication",
            "Dyeline / Dieline Design", "Print Vendor Coordination",
        ],
        "bonus_skills": [
            "FMCG Packaging Design (Food/Beverage)",
            "Visual Hierarchy & Storytelling",
            "Export Market Design Experience",
        ],
        "red_flags": [
            "No Adobe Creative Suite proficiency (Illustrator + Photoshop mandatory)",
            "No packaging design experience",
            "No FMCG commercial design portfolio",
        ],
        "scoring_note": (
            "PACKAGING DESIGN is the primary skill — not general graphic design. "
            "Adobe Illustrator + Photoshop + InDesign are ALL mandatory. "
            "Candidates without an FMCG packaging portfolio should cap at 55 on skills_score. "
            "Understanding of print-ready files and working with print vendors is explicit. "
            "Portfolio evaluation is more important than years of experience for this role."
        ),
        "weight_skills": 65, "weight_exp": 20, "weight_edu": 5,
        "weight_leadership": 0, "weight_culture": 10,
    },

    "Brand-MediaCoordinator": {
        "job_title":         "Media Marketing Production / Digital Media Coordinator",
        "department":        "Brand & Marketing",
        "location":          "Dhaka",
        "deadline":          "19 Aug 2025",
        "experience":        "1 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Bachelor's (flexible for deserving candidates)",
        "min_experience":    "1 year",
        "required_skills": [
            "Adobe Premiere Pro", "CapCut",
            "Adobe Photoshop OR Illustrator OR Canva",
            "Instagram/Facebook/TikTok/LinkedIn/YouTube Management",
            "OVC (Online Video Commercial) Coordination",
            "Creative Agency Coordination", "Brand Standards Review",
            "Behind-the-Scenes Content Capture",
        ],
        "bonus_skills": [
            "AI-Based Creative Tools", "On-Set Production Coordination",
            "Campaign Brief Execution", "Social Media Analytics",
        ],
        "red_flags": [
            "No Adobe Premiere Pro or CapCut experience",
            "No on-ground shoot coordination experience",
            "No social media platform management",
        ],
        "scoring_note": (
            "On-ground coordinator role for OVC shoots and digital campaigns. "
            "Adobe Premiere Pro AND CapCut are both required — these are explicitly stated. "
            "Willingness to travel within Dhaka for shoots is mandatory. "
            "Passion for digital marketing and AI tools is explicitly mentioned. "
            "Education is flexible for the most deserving candidate."
        ),
        "weight_skills": 60, "weight_exp": 20, "weight_edu": 5,
        "weight_leadership": 5, "weight_culture": 10,
    },

    # ── PRODUCTION ─────────────────────────────────────────────────────────────

    "Production-Officer-Carton": {
        "job_title":         "Officer - Production (Carton)",
        "department":        "Production",
        "location":          "Narayanganj",
        "deadline":          "31 Aug 2025",
        "experience":        "2 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "BSc or MSc (any relevant science/engineering)",
        "min_experience":    "2 years",
        "required_skills": [
            "Carton Production Process", "Machine SOP",
            "Corrugated Board Making", "Printing (Carton)",
            "Folder Gluer Operations", "Quality Control",
            "ERP-SAP", "MS Office", "KPI", "5S",
        ],
        "bonus_skills": [
            "R&D", "Production Compliance", "Waste Control",
        ],
        "red_flags": [
            "No carton/packaging production experience",
            "No knowledge of SAP/ERP",
        ],
        "scoring_note": (
            "Packaging production role — carton/corrugated board experience is essential. "
            "SAP/ERP knowledge is explicitly required. 5S methodology knowledge expected."
        ),
        "weight_skills": 50, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Production-Officer-Chanachur": {
        "job_title":         "Officer - Production (Chanachur)",
        "department":        "Production",
        "location":          "Narayanganj",
        "deadline":          "15 Aug 2025",
        "experience":        "2 to 5 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 50,000/month",
        "education_req":     "BSc Food & Nutrition / Bachelor/Master Food Engineering or Food Technology",
        "min_experience":    "2 years",
        "required_skills": [
            "Chanachur/Snack Production Process", "Frying Techniques",
            "Seasoning Application", "Mixing & Blending",
            "GMP", "HACCP", "ISO 22000", "5S", "TQM", "Lean Manufacturing",
            "Quality Control", "Shift Management", "Inventory Control",
        ],
        "bonus_skills": [
            "Six Sigma", "Process Development", "New Product R&D",
        ],
        "red_flags": [
            "No food production experience",
            "No GMP/HACCP knowledge",
        ],
        "scoring_note": (
            "Chanachur (spicy snack) production — frying and seasoning process knowledge is core. "
            "Food science/engineering background is required. GMP/HACCP mandatory."
        ),
        "weight_skills": 50, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Production-Officer-Cookies": {
        "job_title":         "Asst. Officer / Officer - Production (Cookies)",
        "department":        "Production",
        "location":          "Narayanganj",
        "deadline":          "31 Dec 2025",
        "experience":        "2 to 4 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 22,000 – 45,000/month",
        "education_req":     "MSc in Food Engineering / Food Technology / Nutrition & Food Science",
        "min_experience":    "2 years",
        "required_skills": [
            "Biscuit & Cookies Production Process", "Machinery & Equipment Management",
            "Quality Control", "Production Operation", "Troubleshooting",
            "Production Compliance", "SAP-ERP", "MS Office", "KPI", "5S",
        ],
        "bonus_skills": [
            "Six Sigma", "Lean Manufacturing", "Waste Reduction",
        ],
        "red_flags": [
            "No biscuit/cookies production experience",
            "No ERP-SAP knowledge",
        ],
        "scoring_note": (
            "MSc in Food Engineering/Technology/Nutrition is the stated education requirement — "
            "candidates without it should have education_score capped at 50. "
            "Biscuit & cookies process experience is specifically preferred."
        ),
        "weight_skills": 50, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Production-Officer-Chocolate": {
        "job_title":         "Asst. Officer / Officer - Production (Chocolate)",
        "department":        "Production",
        "location":          "Narayanganj",
        "deadline":          "20 Aug 2025",
        "experience":        "2 to 5 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 22,000 – 50,000/month",
        "education_req":     "BSc/MSc in Food Engineering / Food Technology / Nutrition & Food Science",
        "min_experience":    "2 years",
        "required_skills": [
            "Chocolate Production Process", "Mixing & Molding & Tempering & Cooling",
            "Packaging Line Management", "GMP", "HACCP", "5S",
            "FSSC 22000", "HALAL Compliance", "PPE Compliance",
            "Machine SOP", "Quality Control", "R&D",
        ],
        "bonus_skills": [
            "Chocolate Tempering Expertise", "Confectionery R&D",
            "FSSC 22000 Lead Auditor",
        ],
        "red_flags": [
            "No chocolate or confectionery experience",
            "No food safety certifications (GMP/HACCP/FSSC)",
        ],
        "scoring_note": (
            "Chocolate/confectionery production specialist. HALAL compliance and "
            "FSSC 22000 are explicitly required — strong differentiators. "
            "Tempering and molding process knowledge is highly specific."
        ),
        "weight_skills": 50, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Production-AsstManager-Chanachur": {
        "job_title":         "Assistant Manager - Production (Chanachur Plant)",
        "department":        "Production",
        "location":          "Narayanganj",
        "deadline":          "10 Mar 2025",
        "experience":        "10 to 12 years",
        "salary_stated":     "Tk. 70,000 – 140,000 (Monthly)",
        "salary_estimate":   "BDT 70,000 – 140,000/month",
        "education_req":     "Master in Food Technology",
        "min_experience":    "10 years",
        "required_skills": [
            "Chanachur Plant Production Oversight", "Production Scheduling",
            "Process Optimization", "Resource Allocation Management",
            "GMP", "HACCP", "ISO 22000", "5S", "TQM", "Lean Manufacturing",
            "Shift Management", "Staff Management", "Inventory Control",
            "Performance Reporting to Senior Management",
        ],
        "bonus_skills": [
            "Six Sigma", "Process Development", "New Product Industrialization",
        ],
        "red_flags": [
            "No FMCG manufacturing leadership experience",
            "Less than 10 years total experience",
            "No team management (5+ people)",
        ],
        "scoring_note": (
            "Senior production management role — SALARY IS STATED: Tk. 70,000–140,000. "
            "Master's in Food Technology is explicitly required. "
            "Candidates without it should have education_score capped at 50. "
            "Must demonstrate leadership of a full production plant, not just a line."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 10, "weight_culture": 5,
    },

    "Production-AsstManager-Plastic": {
        "job_title":         "Assistant Manager - Plastic Production",
        "department":        "Plastic Production",
        "location":          "Narayanganj",
        "deadline":          "31 Dec 2025",
        "experience":        "6 to 8 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 60,000 – 100,000/month",
        "education_req":     "BSc Mechanical Engineering (Graduate from reputed university)",
        "min_experience":    "6 years",
        "required_skills": [
            "Plastic Injection Molding", "Blow Molding", "PET Sheet Production",
            "Thermoforming Production", "Packing Processes",
            "Quality Management System", "Mold Development & Testing",
            "ERP (SAP preferred)", "Production Planning",
            "Preventive Maintenance Scheduling",
        ],
        "bonus_skills": [
            "Food Industry Plastic Experience", "Lean Manufacturing",
            "Six Sigma", "Plastics Engineering",
        ],
        "red_flags": [
            "No injection molding or blow molding experience",
            "No quality management system knowledge",
            "Not from Mechanical Engineering background",
        ],
        "scoring_note": (
            "BSc Mechanical Engineering from a reputed university is explicit requirement. "
            "Injection molding AND blow molding AND PET experience is a must-have combination. "
            "Food industry plastic experience adds significant value."
        ),
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Production-GM-Wrapper": {
        "job_title":         "General Manager - Wrapper Production",
        "department":        "Production",
        "location":          "Narayanganj",
        "deadline":          "07 Nov 2025",
        "experience":        "15 to 25 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 150,000 – 300,000/month",
        "education_req":     "BSc/MSc in IPE or Mechanical Engineering",
        "min_experience":    "15 years",
        "required_skills": [
            "Wrapper Production Management", "Printing Machine Operations",
            "Lamination Processes", "Cutting & Pouching Machines",
            "Production Schedule Development", "Manpower Planning",
            "Quality Standards for Printed & Laminated Materials",
            "Food-Grade Packaging Compliance", "Cost Control",
            "Safety & Statutory Compliance",
        ],
        "bonus_skills": [
            "Packaging Materials Expertise", "Printing Inks Knowledge",
            "Biscuit Packing Line Coordination",
        ],
        "red_flags": [
            "No wrapper/packaging production management",
            "Less than 15 years total experience",
            "No large-scale production team leadership (50+ people)",
        ],
        "scoring_note": (
            "GM-level role requiring 15-25 years. Packaging and printing expertise is niche. "
            "Must show enterprise-level production leadership with P&L responsibility context. "
            "IPE (Industrial & Production Engineering) or Mechanical Engineering mandatory."
        ),
        "weight_skills": 35, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 20, "weight_culture": 5,
    },

    # ── QUALITY ASSURANCE ─────────────────────────────────────────────────────

    "QA-Officer": {
        "job_title":         "Officer - QA",
        "department":        "Quality Assurance Department (QAD)",
        "location":          "Narayanganj",
        "deadline":          "10 Jun 2025",
        "experience":        "3 to 5 years",
        "salary_stated":     "Tk. 30,000 – 50,000 (Monthly)",
        "salary_estimate":   "BDT 30,000 – 50,000/month",
        "education_req":     "BSc/MSc in Chemistry or Food Technology",
        "min_experience":    "3 years",
        "required_skills": [
            "Raw Material & Finished Goods Testing", "Physical Chemical Microbiological Tests",
            "SOP Development", "QA KPI Tracking & Reporting",
            "ERP", "MS Office",
            "Good knowledge of Chanachur/Noodles/Chips/Puffed Rice/Shemai",
        ],
        "bonus_skills": [
            "Laboratory Management", "New Test Procedure Development",
            "FMCG Snack Category QA",
        ],
        "red_flags": [
            "No laboratory testing experience",
            "No chemistry or food science background",
        ],
        "scoring_note": (
            "SALARY STATED: Tk. 30,000–50,000. Chemistry/Food Technology degree is mandatory. "
            "Specific product knowledge (Chanachur, Chips, Noodles, Puffed Rice) is a stated requirement. "
            "Must perform both internal lab and external lab coordination."
        ),
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "QA-AsstOfficer-Lab": {
        "job_title":         "Assistant Officer - QA (Lab)",
        "department":        "Quality Assurance Department (QAD)",
        "location":          "Narayanganj",
        "deadline":          "31 Dec 2025",
        "experience":        "2 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 20,000 – 35,000/month",
        "education_req":     "BSc/MSc in Chemistry",
        "min_experience":    "2 years",
        "required_skills": [
            "Lab Testing (Raw & Finished Products)", "Equipment Operation & Maintenance",
            "Sampling & Documentation", "Monitoring & Reporting",
            "GMP", "HACCP", "Food Safety", "Good Laboratory Practice (GLP)",
            "RM/PM Certification as per Standard",
        ],
        "bonus_skills": [
            "FSSC 22000", "Microbiological Testing",
            "In-Process Quality Checks",
        ],
        "red_flags": [
            "No laboratory testing experience",
            "No GMP/HACCP knowledge",
            "Not from Chemistry background",
        ],
        "scoring_note": (
            "BSc/MSc Chemistry is mandatory. GLP (Good Laboratory Practice) execution is a core duty. "
            "Incoming RM/PM certification and in-process quality checks are key responsibilities."
        ),
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "QA-HeadOfQA": {
        "job_title":         "Head of QA",
        "department":        "Quality Assurance Department (QAD)",
        "location":          "Narayanganj",
        "deadline":          "20 Jun 2025",
        "experience":        "At least 15 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 150,000 – 280,000/month",
        "education_req":     "Master in Chemistry / Bio-Chemistry / Food Technology / Microbiology",
        "min_experience":    "15 years",
        "required_skills": [
            "Quality Planning", "QA Policy Making", "Quality Culture Management",
            "Food Safety & Quality Management System",
            "Compliance with Regulatory Requirements",
            "New Product & Process Development Support",
            "ERP", "MS Office",
        ],
        "bonus_skills": [
            "FSSC 22000 / ISO 22000 Certification Management",
            "FMCG Head of QA Experience",
            "HACCP Lead Auditor",
        ],
        "red_flags": [
            "Less than 15 years in QA",
            "No food safety management system ownership",
            "Not from Chemistry/Food Technology/Microbiology background",
        ],
        "scoring_note": (
            "C-level functional head. Must show ownership of the entire QA system, not just execution. "
            "Master's degree in Chemistry, Biochemistry, Food Technology, or Microbiology is mandatory. "
            "15+ years with progressive leadership in FMCG QA is the benchmark."
        ),
        "weight_skills": 35, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 15, "weight_culture": 5,
    },

    # ── ENGINEERING ────────────────────────────────────────────────────────────

    "Engineering-AsstEngineer-Electrical": {
        "job_title":         "Assistant Engineer - Electrical",
        "department":        "Engineering",
        "location":          "Narayanganj",
        "deadline":          "07 Nov 2025",
        "experience":        "1 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 55,000/month",
        "education_req":     "Not stated (FMCG Manufacturing experience required)",
        "min_experience":    "1 year",
        "required_skills": [
            "Electrical Maintenance (FMCG Machinery)", "Erection/Installation/Commissioning",
            "AutoCAD", "OEE (Overall Equipment Efficiency)", "Troubleshooting",
            "Systems Analysis", "Technology Design", "Compliance",
            "Technical Documentation",
        ],
        "bonus_skills": [
            "Food Processing Line Experience",
            "Preventive Maintenance", "Project Budget Estimation",
        ],
        "red_flags": [
            "No FMCG electrical maintenance experience",
            "No AutoCAD skills",
            "No commissioning experience",
        ],
        "scoring_note": (
            "Food processing factory electrical role. AutoCAD is explicitly required. "
            "FMCG machinery electrical maintenance is the core experience needed. "
            "Project management and budget estimation skills are also stated."
        ),
        "weight_skills": 55, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Engineering-AsstEngineer-Mechanical": {
        "job_title":         "Assistant Engineer / Engineer - Mechanical",
        "department":        "Engineering",
        "location":          "Narayanganj",
        "deadline":          "07 Nov 2025",
        "experience":        "1 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 55,000/month",
        "education_req":     "Not stated (FMCG Manufacturing experience required)",
        "min_experience":    "1 year",
        "required_skills": [
            "Production Machinery Maintenance", "Erection/Installation/Commissioning",
            "ISO Standard Factory Development", "CAD Technology",
            "Problem Analysis & Solution Development",
            "OEE", "Troubleshooting", "Systems Analysis",
        ],
        "bonus_skills": [
            "Food Processing Line Experience",
            "Mechanical Design", "Predictive Maintenance",
        ],
        "red_flags": [
            "No FMCG manufacturing environment experience",
            "No CAD skills",
        ],
        "scoring_note": (
            "FMCG factory mechanical maintenance with ISO standards compliance. "
            "CAD design skills are explicitly required. "
            "Collaborative work in a fast-paced manufacturing environment is emphasized."
        ),
        "weight_skills": 55, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    "Engineering-Manager-Mechanical": {
        "job_title":         "Manager / Sr. Manager - Mechanical",
        "department":        "Engineering",
        "location":          "Narayanganj",
        "deadline":          "22 Jul 2025",
        "experience":        "10 to 15 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 100,000 – 200,000/month",
        "education_req":     "BSc/MSc in Mechanical Engineering",
        "min_experience":    "10 years",
        "required_skills": [
            "Preventive & Predictive & Corrective Maintenance",
            "CAD Software for Mechanical Design",
            "Root Cause Analysis", "Mechanical Failure Troubleshooting",
            "Spare Parts Inventory Management",
            "Mechanical System Design for New Production Lines",
            "Project Management",
        ],
        "bonus_skills": [
            "Lean Manufacturing", "Six Sigma",
            "FMCG Plant Maintenance Management",
            "Industrial Automation",
        ],
        "red_flags": [
            "No FMCG/manufacturing maintenance management experience",
            "Less than 10 years total experience",
            "No CAD proficiency",
        ],
        "scoring_note": (
            "Senior mechanical engineering manager. CAD proficiency is explicitly required. "
            "Must show enterprise-level predictive + preventive maintenance programme ownership. "
            "Lean/Six Sigma is a plus but root cause analysis and failure resolution are core."
        ),
        "weight_skills": 40, "weight_exp": 30, "weight_edu": 15,
        "weight_leadership": 10, "weight_culture": 5,
    },

    "Engineering-ProjectEngineer": {
        "job_title":         "Project Engineer / Structural Engineer",
        "department":        "Engineering",
        "location":          "Narayanganj",
        "deadline":          "31 Oct 2025",
        "experience":        "4 to 8 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 50,000 – 100,000/month",
        "education_req":     "BSc in Civil Engineering",
        "min_experience":    "4 years",
        "required_skills": [
            "RCC Construction", "Steel Erection", "Quality Supervision",
            "Staadpro", "ETABS", "Tekla", "RAM Connection", "AutoCAD (2D/3D)",
            "Construction Methodology", "Piling",
            "Structural Analysis & Design",
        ],
        "bonus_skills": [
            "BNBC-2020 Compliance", "ACI Standards", "NFPA", "ASCE",
            "Sub-contractor Bill Verification",
        ],
        "red_flags": [
            "No civil/structural engineering experience",
            "No Staadpro or ETABS software experience",
            "No RCC construction project management",
        ],
        "scoring_note": (
            "Two vacancies: one Project Engineer (construction management), one Structural Engineer (design). "
            "Both require BSc Civil Engineering. Software expertise is critical: "
            "Staadpro + ETABS + Tekla + AutoCAD are explicitly required tools. "
            "BNBC-2020, ACI, NFPA, ASCE compliance knowledge is required for Structural role."
        ),
        "weight_skills": 55, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 0,
    },

    # ── STORE ──────────────────────────────────────────────────────────────────

    "Store-OfficerSr": {
        "job_title":         "Officer / Sr. Officer - Store",
        "department":        "Store",
        "location":          "Narayanganj",
        "deadline":          "31 Jan 2026",
        "experience":        "5 to 7 years (Construction/Real Estate)",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 55,000/month",
        "education_req":     "BCom/Bachelor/Master in Accounting / Finance / SCM",
        "min_experience":    "5 years",
        "required_skills": [
            "Inventory Management", "Warehouse Operations",
            "Record Keeping & Documentation", "SAP-ERP (Inventory Module)",
            "Daily Material In/Out Stock Reports",
            "Gate Pass Management", "PR (Purchase Requisition) Raising",
        ],
        "bonus_skills": [
            "Construction/Real Estate Inventory Context",
            "Material Inspection", "FIFO/FEFO",
        ],
        "red_flags": [
            "No SAP-ERP inventory experience",
            "No store/warehouse operations experience",
        ],
        "scoring_note": (
            "NOTE: This role specifically mentions Construction/Real Estate experience. "
            "Candidates from that context are prioritized. SAP-ERP inventory module is mandatory. "
            "Daily reporting of material in/out is a core duty."
        ),
        "weight_skills": 45, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "Store-Manager": {
        "job_title":         "Manager / Sr. Manager - Store",
        "department":        "Store",
        "location":          "Narayanganj",
        "deadline":          "28 Feb 2025",
        "experience":        "10 to 12 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 80,000 – 140,000/month",
        "education_req":     "Bachelor/Master in Accounting / Finance / SCM",
        "min_experience":    "10 years",
        "required_skills": [
            "Inventory Management & Control", "Warehouse Operations",
            "SAP-ERP", "Record Keeping & Documentation",
            "Material & Inventory Policy Compliance",
            "SOP Enforcement", "Store Operations Management",
        ],
        "bonus_skills": [
            "FMCG Food Industry Store Experience",
            "High-SKU Environment Management",
            "Team Leadership",
        ],
        "red_flags": [
            "No FMCG (food industry) preference noted if missing",
            "No SAP experience",
            "Less than 10 years total experience",
        ],
        "scoring_note": (
            "Senior store management role. FMCG (food industry) experience is explicitly preferred. "
            "SAP-ERP is mandatory. Must show team management and policy compliance enforcement "
            "at a factory/warehouse level, not just office supplies management."
        ),
        "weight_skills": 40, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 10, "weight_culture": 5,
    },

    # ── SUPPLY CHAIN / PROCUREMENT ─────────────────────────────────────────────

    "SupplyChain-JrExecutive": {
        "job_title":         "Jr. Executive / Executive - Supply Chain",
        "department":        "Supply Chain",
        "location":          "Narayanganj",
        "deadline":          "12 Oct 2025",
        "experience":        "2 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Diploma Mechanical/Electrical OR BBA",
        "min_experience":    "2 years",
        "required_skills": [
            "Machinery Parts Knowledge", "ERP-SAP", "Price Quotation Collection",
            "Comparative Statement Preparation", "Delivery Coordination",
            "Factory Engineering Team Coordination",
            "Negotiation & Communication",
        ],
        "bonus_skills": [
            "Machinery & Spare Parts Sourcing",
            "Vendor Management",
        ],
        "red_flags": [
            "No machinery/spare parts supply experience",
            "No SAP/ERP knowledge",
        ],
        "scoring_note": (
            "Engineering spare parts supply chain role — primarily supports factory maintenance teams. "
            "Clear knowledge of machineries and parts is explicitly required. "
            "Diploma in Mechanical/Electrical Engineering is accepted alongside BBA."
        ),
        "weight_skills": 45, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "Procurement-SrExecutive": {
        "job_title":         "Sr. Executive / Asst. Manager - Procurement",
        "department":        "Supply Chain",
        "location":          "Dhaka",
        "deadline":          "15 Jan 2025",
        "experience":        "3 to 6 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 45,000 – 80,000/month",
        "education_req":     "Graduation in any discipline (SCM degree preferred)",
        "min_experience":    "3 years",
        "required_skills": [
            "Procurement Planning", "Vendor Sourcing & Vendor Pool Creation",
            "Quotation Collection & Negotiation",
            "Comparative Statement & Approval Process",
            "Purchase Order Issuance", "Market Price Verification",
            "Supplier Factory Visits", "Delivery Follow-up",
            "ERP", "MS Office",
        ],
        "bonus_skills": [
            "Supply Chain Management Degree",
            "FMCG Procurement", "Supplier Capacity Assessment",
        ],
        "red_flags": [
            "No procurement experience",
            "No negotiation skills evidence",
            "Age requirement: 27-33 years (from posting)",
        ],
        "scoring_note": (
            "End-to-end procurement role with vendor sourcing and PO management. "
            "SCM degree is preferred. Supplier factory visits are part of the job. "
            "Age requirement in posting: 27-33 years — note as soft filter, not hard reject."
        ),
        "weight_skills": 45, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    # ── DELIVERY ───────────────────────────────────────────────────────────────

    "Delivery-Manager": {
        "job_title":         "Manager / Sr. Manager - Delivery",
        "department":        "Delivery",
        "location":          "Narayanganj",
        "deadline":          "15 Mar 2026",
        "experience":        "7 to 10 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 80,000 – 150,000/month",
        "education_req":     "Graduation/Post Graduation in Finance / Accounts / SCM / Management",
        "min_experience":    "7 years",
        "required_skills": [
            "Delivery Strategy & Planning", "SAP", "VAT Software",
            "VAT Compliance", "VAT Policy & Procedure",
            "Delivery Operations Monitoring", "Customer Satisfaction Management",
            "Team Leadership & Coaching", "End-to-End Delivery Management",
        ],
        "bonus_skills": [
            "FMCG Delivery Operations",
            "Route Optimization",
            "Cost & Quality Management",
        ],
        "red_flags": [
            "No VAT compliance experience",
            "No SAP experience",
            "No delivery/logistics team leadership",
        ],
        "scoring_note": (
            "Senior delivery operations role. VAT compliance and SAP are explicitly required — "
            "unusual for a delivery role, likely due to the VAT & Delivery nature of Olympic's operations. "
            "Team coaching and continuous improvement are stated deliverables."
        ),
        "weight_skills": 40, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 10, "weight_culture": 5,
    },

    # ── IMPORT ─────────────────────────────────────────────────────────────────

    "Import-ExecutiveSr": {
        "job_title":         "Executive / Sr. Executive - Import",
        "department":        "Import",
        "location":          "Dhaka",
        "deadline":          "03 Oct 2025",
        "experience":        "1 to 3 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 55,000/month",
        "education_req":     "BBA / Graduation",
        "min_experience":    "1 year",
        "required_skills": [
            "Letter of Credit (LC) Management", "Import Documentation",
            "Customs Compliance", "Shipment Tracking",
            "Supplier & Bank Liaison", "LC Clause Review (Bangladesh Import Policy)",
            "Payment Follow-up", "ERP", "MS Office",
        ],
        "bonus_skills": [
            "FMCG Import Experience",
            "Foreign Currency Management",
            "Freight Forwarding",
        ],
        "red_flags": [
            "No LC management experience",
            "No import documentation experience",
        ],
        "scoring_note": (
            "Specialist LC and import documentation role. "
            "Bangladesh Import Policy LC clause review is a specific technical skill required. "
            "Fluent typing in both English and Bangla is explicitly stated."
        ),
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 5,
    },

    # ── FIELD FORCE / SALES ────────────────────────────────────────────────────

    "FieldForce-ExecutiveSr": {
        "job_title":         "Executive / Sr. Executive - Field Force Operations",
        "department":        "Field Force",
        "location":          "Dhaka",
        "deadline":          "05 Apr 2026",
        "experience":        "1 to 3 years (Freshers encouraged)",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 30,000 – 55,000/month",
        "education_req":     "BBA in HR/Management/Marketing (MBA advantage)",
        "min_experience":    "Any",
        "required_skills": [
            "Advanced Microsoft Excel (incl. advanced functions, data analysis)",
            "Attendance & Leave Record Management",
            "Field Force Database Management",
            "Recruitment Documentation & Onboarding Coordination",
            "Employee Separation Processing",
            "Reporting & Dashboard Preparation",
        ],
        "bonus_skills": [
            "ERP/SAP/SFA Systems", "Field Force Management Experience",
            "Sales Administration", "MBA",
        ],
        "red_flags": [
            "No advanced Excel proficiency",
            "No HR administration or sales operations experience",
        ],
        "scoring_note": (
            "This is an OPERATIONS/ADMIN role for the field sales team — NOT a field sales role. "
            "Advanced Excel is the primary skill explicitly required. "
            "Coordination with Sales, MIS, Market Audit, and Marketing teams is the core job. "
            "Freshers from good universities with strong Excel skills are explicitly welcome."
        ),
        "weight_skills": 50, "weight_exp": 25, "weight_edu": 15,
        "weight_leadership": 5, "weight_culture": 5,
    },

    "MarketAudit-Executive": {
        "job_title":         "Executive - Market Audit",
        "department":        "Market Audit",
        "location":          "Dhaka",
        "deadline":          "18 Mar 2025",
        "experience":        "1 to 2 years",
        "salary_stated":     "Negotiable",
        "salary_estimate":   "BDT 25,000 – 45,000/month",
        "education_req":     "Bachelor / MA / M.COM / MSC / MBA",
        "min_experience":    "1 year",
        "required_skills": [
            "Market Visits & Gap Analysis", "Stock Counting & Reconciliation",
            "Product Presence & Stock Status Monitoring",
            "Market Share & Coverage Analysis",
            "Audit Report Preparation", "Internal Process Investigation",
            "Marketing Campaign Audit", "ERP", "MS Office",
        ],
        "bonus_skills": [
            "FMCG Field Market Audit",
            "Distributor/Dealer Audit",
            "Competitor Analysis",
        ],
        "red_flags": [
            "No field visit / market audit experience",
            "No FMCG distribution channel knowledge",
            "Unwillingness to travel",
        ],
        "scoring_note": (
            "Field-heavy role requiring regular market visits — willingness to travel is mandatory. "
            "SKU-wise product availability survey and stock reconciliation are core activities. "
            "Marketing campaign audit is a unique dual-function aspect."
        ),
        "weight_skills": 40, "weight_exp": 35, "weight_edu": 10,
        "weight_leadership": 5, "weight_culture": 10,
    },
}

