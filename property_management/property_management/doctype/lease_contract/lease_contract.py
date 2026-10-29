# Copyright (c) 2026, Savio Fernandes and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint


class LeaseContract(Document):
	def validate(self):
		self.validate_pdc_details()
		self.calculate_pdc_amounts()

	def validate_pdc_details(self):
		"""Validate PDC details if payment mode is Cheque or Mixed"""
		if self.payment_mode in ["Cheque", "Mixed"] and self.number_of_pdcs:
			if not self.pdcs_table or len(self.pdcs_table) != self.number_of_pdcs:
				frappe.throw(f"Please provide exactly {self.number_of_pdcs} PDC entries")

			total_pdc_amount = sum(flt(row.amount) for row in self.pdcs_table)
			if total_pdc_amount != flt(self.contract_value):
				frappe.throw(
					f"Total PDC amount ({total_pdc_amount}) must equal Contract Value ({self.contract_value})"
				)

	def calculate_pdc_amounts(self):
		"""Auto-divide contract value equally among PDCs"""
		if self.payment_mode in ["Cheque", "Mixed"] and self.number_of_pdcs and self.contract_value:
			if not self.pdcs_table or len(self.pdcs_table) != self.number_of_pdcs:
				self.pdcs_table = []
				amount_per_pdc = flt(self.contract_value) / cint(self.number_of_pdcs)

				for i in range(1, cint(self.number_of_pdcs) + 1):
					self.append("pdcs_table", {
						"cheque_number": "",
						"cheque_date": "",
						"bank_name": "",
						"amount": amount_per_pdc,
						"status": "Pending"
					})

	@frappe.whitelist()
	def generate_pdc_rows(self):
		"""Client-callable method to generate PDC rows"""
		if not self.number_of_pdcs or not self.contract_value:
			return

		self.pdcs_table = []
		amount_per_pdc = flt(self.contract_value) / cint(self.number_of_pdcs)

		for i in range(1, cint(self.number_of_pdcs) + 1):
			self.append("pdcs_table", {
				"cheque_number": "",
				"cheque_date": "",
				"bank_name": "",
				"amount": amount_per_pdc,
				"status": "Pending"
			})

		return self.pdcs_table