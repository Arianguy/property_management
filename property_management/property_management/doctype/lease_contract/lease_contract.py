# Copyright (c) 2026, Savio Fernandes and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint


class LeaseContract(Document):
	def validate(self):
		self.validate_pdc_details()
		self.validate_cash_plan()
		self.validate_bank_transfer_plan()
		self.validate_security_deposit_plan()
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
			
			# Validate mandatory cheque copy
			for row in self.pdcs_table:
				if not row.cheque_copy:
					frappe.throw(f"Row {row.idx}: Cheque Copy is mandatory for PDC")

	def validate_cash_plan(self):
		"""Validate Cash Plan details"""
		if self.payment_mode in ["Cash", "Mixed"] and self.cash_plan_table:
			total_cash_amount = sum(flt(row.amount) for row in self.cash_plan_table)
			# For mixed mode, cash amount should be part of contract value
			if self.payment_mode == "Mixed":
				pass  # Will be validated in combined validation
			elif total_cash_amount != flt(self.contract_value):
				frappe.throw(
					f"Total Cash Plan amount ({total_cash_amount}) must equal Contract Value ({self.contract_value})"
				)

	def validate_bank_transfer_plan(self):
		"""Validate Bank Transfer Plan details"""
		if self.payment_mode in ["Bank Transfer", "Mixed"] and self.bank_transfer_plan_table:
			total_bank_amount = sum(flt(row.amount) for row in self.bank_transfer_plan_table)
			if self.payment_mode == "Bank Transfer" and total_bank_amount != flt(self.contract_value):
				frappe.throw(
					f"Total Bank Transfer Plan amount ({total_bank_amount}) must equal Contract Value ({self.contract_value})"
				)

	def validate_security_deposit_plan(self):
		"""Validate Security Deposit Plan details"""
		if self.security_deposit > 0 and self.security_deposit_plan_table:
			total_sd_amount = sum(flt(row.amount) for row in self.security_deposit_plan_table)
			if total_sd_amount != flt(self.security_deposit):
				frappe.throw(
					f"Total Security Deposit Plan amount ({total_sd_amount}) must equal Security Deposit ({self.security_deposit})"
				)
			
			# Validate mandatory fields per payment mode
			for row in self.security_deposit_plan_table:
				if row.payment_mode == "Cheque" and (not row.cheque_number or not row.cheque_date or not row.cheque_copy):
					frappe.throw(f"Security Deposit Row {row.idx}: Cheque Number, Date and Copy are mandatory for Cheque mode")
				elif row.payment_mode == "Bank Transfer" and (not row.transaction_id or not row.bank_account):
					frappe.throw(f"Security Deposit Row {row.idx}: Transaction ID and Bank Account are mandatory for Bank Transfer mode")

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
						"cheque_copy": ""
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
				"cheque_copy": ""
			})

		return self.pdcs_table

	@frappe.whitelist()
	def generate_security_deposit_row(self):
		"""Auto-generate security deposit plan row based on security_deposit_mode"""
		if not self.security_deposit_mode or not self.security_deposit:
			return

		# Clear existing rows
		self.security_deposit_plan_table = []

		# Add one row with the selected mode and amount
		row = {
			"payment_mode": self.security_deposit_mode,
			"amount": self.security_deposit
		}

		# Set mode-specific defaults
		if self.security_deposit_mode == "Cheque":
			row.update({
				"cheque_number": "",
				"cheque_date": "",
				"bank_name": "",
				"cheque_copy": ""
			})
		elif self.security_deposit_mode == "Cash":
			row.update({
				"receipt_number": ""
			})
		elif self.security_deposit_mode == "Bank Transfer":
			row.update({
				"transaction_id": "",
				"bank_account": "",
				"reference_number": ""
			})

		self.append("security_deposit_plan_table", row)
		return self.security_deposit_plan_table

	def on_submit(self):
		"""Auto-create all receipts and update property status on submit"""
		self.create_receipts()
		self.update_property_status("LEASED")

	def on_cancel(self):
		"""Cancel linked receipts and reset property status on cancel"""
		self.cancel_receipts()
		self.update_property_status("VACANT")

	def create_receipts(self):
		"""Create all receipts from plan tables"""
		from property_management.property_management.doctype.lease_contract_receipt.lease_contract_receipt import make_receipts_from_plan
		
		receipts = make_receipts_from_plan(self.name)
		
		if not receipts:
			frappe.throw("No receipts could be created. Please fill in all plan details before submitting.")

	def cancel_receipts(self):
		"""Cancel all linked receipts, but PRESERVE:
		- PDC: Deposited, Cleared (with Payment Entry)
		- Cash/Bank Transfer: Received (Submitted)
		- Security Deposit: Cash/Bank Transfer (Submitted)"""
		receipts = frappe.get_all("Lease Contract Receipt", 
			filters={"lease_contract": self.name, "docstatus": ["in", [0, 1]]})
		
		preserved_count = 0
		cancelled_count = 0
		
		for r in receipts:
			doc = frappe.get_doc("Lease Contract Receipt", r.name)
			preserve = False
			
			# PRESERVE: PDC - Deposited or Cleared (with Payment Entry)
			if doc.payment_mode == "PDC" and doc.pdc_status in ["Deposited", "Cleared"]:
				if doc.pdc_status == "Cleared" and doc.clearing_entry:
					preserve = True
				elif doc.pdc_status == "Deposited" and doc.deposit_entry:
					preserve = True
			
			# PRESERVE: Cash/Bank Transfer - Received (Submitted)
			if doc.payment_mode in ["Cash", "Bank Transfer"] and doc.docstatus == 1:
				preserve = True
			
			# PRESERVE: Security Deposit - Cash/Bank Transfer (Submitted)
			if doc.receipt_type == "Security Deposit" and doc.payment_mode in ["Cash", "Bank Transfer"] and doc.docstatus == 1:
				preserve = True
			
			if preserve:
				preserved_count += 1
				continue
				
			# Cancel/Delete other receipts
			if doc.docstatus == 1:
				doc.cancel()
			elif doc.docstatus == 0:
				# For Draft receipts, just delete them
				frappe.delete_doc("Lease Contract Receipt", doc.name, force=True)
			cancelled_count += 1
			
			# Clear receipt link from plan tables
			frappe.db.sql("""
				UPDATE `tabLease Contract PDC` SET receipt = NULL WHERE receipt = %s
			""", r.name)
			frappe.db.sql("""
				UPDATE `tabLease Contract Cash Plan` SET receipt = NULL WHERE receipt = %s
			""", r.name)
			frappe.db.sql("""
				UPDATE `tabLease Contract Bank Transfer Plan` SET receipt = NULL WHERE receipt = %s
			""", r.name)
			frappe.db.sql("""
				UPDATE `tabLease Contract Security Deposit Plan` SET receipt = NULL WHERE receipt = %s
			""", r.name)
		
		if preserved_count > 0:
			frappe.msgprint(
				f"{preserved_count} payment(s) preserved (not cancelled). "
				f"{cancelled_count} other receipt(s) cancelled.",
				title="Receipts Processed",
				indicator="orange"
			)

	def update_property_status(self, status):
		"""Update linked property status"""
		if self.lease_property:
			frappe.db.set_value("Property", self.lease_property, "status", status)

	@frappe.whitelist()
	def make_receipts(self):
		"""Create Lease Contract Receipts from all plan tables (for manual use if needed)"""
		self.create_receipts()
		frappe.msgprint(
			f"All receipts created successfully.",
			title="Receipts Created",
			indicator="green"
		)