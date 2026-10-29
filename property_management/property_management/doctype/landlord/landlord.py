# Copyright (c) 2026, Savio Fernandes and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Landlord(Document):
    def validate(self):
        # List of fields you want to format into Title Case
        fields_to_format = [
            "first_name",
            "last_name",
            "nationality",
        ]

        for field in fields_to_format:
            value = getattr(self, field, None)
            if value:
                setattr(self, field, value.strip().title())
