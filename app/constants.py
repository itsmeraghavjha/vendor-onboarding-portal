class WorkflowStage:
    """Defines the high-level phases of the application."""
    INITIATOR_REVIEW = 'INITIATOR_REVIEW'
    DEPT_HEAD = 'DEPT'
    FINANCE = 'FINANCE'
    IT = 'IT'
    
    # End states
    COMPLETED = 'COMPLETED'
    REJECTED = 'REJECTED'
    PENDING_VENDOR = 'PENDING_VENDOR'

class FinanceStage:
    """Sub-stages within the Finance phase."""
    BILL_PASSING = 'BILL_PASSING'
    TREASURY = 'TREASURY'
    TAX = 'TAX'

class Role:
    """User roles for permissions."""
    ADMIN = 'admin'
    INITIATOR = 'initiator'
    DEPT_HEAD = 'dept_head'
    FINANCE = 'finance'
    IT = 'it'