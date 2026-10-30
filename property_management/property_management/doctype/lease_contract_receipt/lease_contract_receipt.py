# Copyright (c) 2026, Savio Fernandes and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class LeaseContractReceipt(Document):
	def before_insert(self):
		"""Auto-generate cash receipt number for Cash payments"""
		if self.payment_mode == "Cash" and not self.cash_receipt_number:
			self.cash_receipt_number = self.generate_cash_receipt_number()

	def validate(self):
		self.set_received_by()
		self.validate_pdc_fields()
		self.validate_cash_fields()
		self.validate_bank_fields()
		self.validate_security_deposit_fields()

	def set_received_by(self):
		if not self.received_by:
			self.received_by = frappe.session.user

	def validate_pdc_fields(self):
		if self.payment_mode == "PDC":
			if not self.cheque_number:
				frappe.throw("Cheque Number is required for PDC")
			if not self.cheque_date:
				frappe.throw("Cheque Date is required for PDC")
			if not self.attachment:
				frappe.throw("Cheque Copy attachment is required for PDC")

	def validate_cash_fields(self):
		if self.payment_mode == "Cash":
			if not self.cash_receipt_number:
				frappe.throw("Cash Receipt Number is required for Cash payment")

	def validate_bank_fields(self):
		if self.payment_mode == "Bank Transfer":
			if not self.transaction_id:
				frappe.throw("Transaction ID is required for Bank Transfer")
			if not self.bank_account:
				frappe.throw("Bank Account is required for Bank Transfer")
			if not self.attachment:
				frappe.throw("Bank Advice attachment is required for Bank Transfer")

	def validate_security_deposit_fields(self):
		if self.receipt_type == "Security Deposit":
			if self.refund_status != "Held" and not self.refund_amount:
				frappe.throw("Refund Amount is required when refund status is not Held")
			if self.refund_status == "Fully Refunded" and not self.refund_date:
				frappe.throw("Refund Date is required for Fully Refunded status")

	def generate_cash_receipt_number(self):
		"""Generate incremental cash receipt number: ASH-001, ASH-002, etc."""
		last_receipt = frappe.db.sql("""
			SELECT cash_receipt_number 
			FROM `tabLease Contract Receipt` 
			WHERE payment_mode = 'Cash' 
			AND cash_receipt_number LIKE 'ASH-%'
			ORDER BY cash_receipt_number DESC 
			LIMIT 1
		""")
		
		if last_receipt and last_receipt[0][0]:
			last_num = int(last_receipt[0][0].split('-')[1])
			new_num = last_num + 1
		else:
			new_num = 1
		
		return f"ASH-{new_num:03d}"

	def on_submit(self):
		"""Auto-create accounting entries on submit"""
		if self.payment_mode == "PDC" and self.pdc_status == "Deposited":
			self.create_deposit_entry()
		elif self.payment_mode == "PDC" and self.pdc_status == "Cleared":
			self.create_clearing_entry()
		elif self.payment_mode in ["Cash", "Bank Transfer"]:
			self.create_payment_entry()
		elif self.receipt_type == "Security Deposit" and self.refund_status != "Held":
			self.create_security_deposit_entry()

	def create_deposit_entry(self):
		"""Create Journal Entry for cheque deposit (Cheques in Hand)"""
		lease_contract = frappe.get_doc("Lease Contract", self.lease_contract)
		
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.posting_date = self.deposited_date or today()
		je.company = lease_contract.company if hasattr(lease_contract, 'company') else frappe.defaults.get_user_default("Company")
		je.remark = f"PDC Deposit - {self.cheque_number} - {self.lease_contract}"
		
		# Get accounts from company defaults or settings
		company = je.company
		cheques_in_hand = frappe.db.get_value("Company", company, "cheques_in_hand_account") or "Cheques in Hand - " + company
		receivable_account = frappe.db.get_value("Company", company, "default_receivable_account") or "Debtors - " + company
		
		je.append("accounts", {
			"account": cheques_in_hand,
			"debit_in_account_currency": self.amount,
			"reference_type": "Lease Contract Receipt",
			"reference_name": self.name
		})
		je.append("accounts", {
			"account": receivable_account,
			"credit_in_account_currency": self.amount,
			"party_type": "Customer",
			"party": lease_contract.tenant,
			"reference_type": "Lease Contract Receipt",
			"reference_name": self.name
		})
		
		je.insert(ignore_permissions=True)
		je.submit()
		
		self.deposit_entry = je.name
		self.db_set("deposit_entry", je.name)

	def create_clearing_entry(self):
		"""Create Payment Entry for cheque clearing"""
		lease_contract = frappe.get_doc("Lease Contract", self.lease_contract)
		
		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.mode_of_payment = "Cheque"
		pe.posting_date = self.cleared_date or today()
		pe.company = lease_contract.company if hasattr(lease_contract, 'company') else frappe.defaults.get_user_default("Company")
		pe.party_type = "Customer"
		pe.party = lease_contract.tenant
		pe.paid_amount = self.amount
		pe.received_amount = self.amount
		pe.reference_no = self.cheque_number
		pe.reference_date = self.cheque_date
		pe.remark = f"PDC Cleared - {self.cheque_number} - {self.lease_contract}"
		
		# Set bank account
		bank_account = frappe.db.get_value("Company", pe.company, "default_bank_account")
		if bank_account:
			pe.paid_to = bank_account
		
		pe.insert(ignore_permissions=True)
		pe.submit()
		
		self.clearing_entry = pe.name
		self.db_set("clearing_entry", pe.name)

	def create_payment_entry(self):
		"""Create Payment Entry for Cash or Bank Transfer"""
		lease_contract = frappe.get_doc("Lease Contract", self.lease_contract)
		
		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.posting_date = self.receipt_date
		pe.company = lease_contract.company if hasattr(lease_contract, 'company') else frappe.defaults.get_user_default("Company")
		pe.party_type = "Customer"
		pe.party = lease_contract.tenant
		pe.paid_amount = self.amount
		pe.received_amount = self.amount
		pe.remark = f"{self.payment_mode} Receipt - {self.lease_contract}"
		
		if self.payment_mode == "Cash":
			pe.mode_of_payment = "Cash"
			cash_account = frappe.db.get_value("Company", pe.company, "default_cash_account")
			if cash_account:
				pe.paid_to = cash_account
		elif self.payment_mode == "Bank Transfer":
			pe.mode_of_payment = "Bank Transfer"
			pe.reference_no = self.transaction_id
			pe.reference_date = self.receipt_date
			if self.bank_account:
				pe.paid_to = self.bank_account
			else:
				bank_account = frappe.db.get_value("Company", pe.company, "default_bank_account")
				if bank_account:
					pe.paid_to = bank_account
		
		pe.insert(ignore_permissions=True)
		pe.submit()
		
		# Link back to receipt
		if self.payment_mode == "Cash":
			self.db_set("cash_receipt_number", pe.name)
		elif self.payment_mode == "Bank Transfer":
			self.db_set("reference_number", pe.name)

	def create_security_deposit_entry(self):
		"""Create Payment Entry for Security Deposit refund/adjustment"""
		lease_contract = frappe.get_doc("Lease Contract", self.lease_contract)
		
		if self.refund_status in ["Fully Refunded", "Partially Refunded"]:
			pe = frappe.new_doc("Payment Entry")
			pe.payment_type = "Pay"
			pe.posting_date = self.refund_date or today()
			pe.company = lease_contract.company if hasattr(lease_contract, 'company') else frappe.defaults.get_user_default("Company")
			pe.party_type = "Customer"
			pe.party = lease_contract.tenant
			pe.paid_amount = self.refund_amount
			pe.remark = f"Security Deposit Refund - {self.lease_contract}"
			
			# Credit to bank/cash account
			bank_account = frappe.db.get_value("Company", pe.company, "default_bank_account")
			if bank_account:
				pe.paid_from = bank_account
			
			pe.insert(ignore_permissions=True)
			pe.submit()
			self.db_set("refund_entry", pe.name)
			
		elif self.refund_status == "Adjusted":
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Journal Entry"
			je.posting_date = today()
			je.company = lease_contract.company if hasattr(lease_contract, 'company') else frappe.defaults.get_user_default("Company")
			je.remark = f"Security Deposit Adjusted - {self.lease_contract}"
			
			company = je.company
			security_deposit_account = frappe.db.get_value("Company", company, "security_deposit_account") or "Security Deposit - " + company
			income_account = frappe.db.get_value("Company", company, "default_income_account") or "Rental Income - " + company
			
			je.append("accounts", {
				"account": security_deposit_account,
				"debit_in_account_currency": self.refund_amount,
				"reference_type": "Lease Contract Receipt",
				"reference_name": self.name
			})
			je.append("accounts", {
				"account": income_account,
				"credit_in_account_currency": self.refund_amount,
				"reference_type": "Lease Contract Receipt",
				"reference_name": self.name
			})
			
			je.insert(ignore_permissions=True)
			je.submit()
			self.db_set("adjustment_entry", je.name)


@frappe.whitelist()
def make_receipts_from_plan(lease_contract_name):
	"""Create Lease Contract Receipts from plan tables based on payment_mode.
	Only creates receipts for rows that don't already have one."""
	lease_contract = frappe.get_doc("Lease Contract", lease_contract_name)
	receipts_created = []
	payment_mode = lease_contract.payment_mode
	
	# For Mixed mode, process all tables that have data
	# For specific mode, only process that mode's table
	process_pdc = payment_mode in ["Cheque", "Mixed"]
	process_cash = payment_mode in ["Cash", "Mixed"]
	process_bank = payment_mode in ["Bank Transfer", "Mixed"]
	process_sd = lease_contract.security_deposit > 0
	
	# Process PDC Plan
	if process_pdc:
		for row in lease_contract.get("pdcs_table", []):
			if row.cheque_number and row.cheque_date and row.cheque_copy:
				# Skip if receipt already exists for this row
				if row.receipt:
					continue
				receipt = frappe.new_doc("Lease Contract Receipt")
				receipt.lease_contract = lease_contract_name
				receipt.receipt_type = "Rent"
				receipt.payment_mode = "PDC"
				receipt.receipt_date = today()
				receipt.amount = row.amount
				receipt.attachment = row.cheque_copy
				receipt.cheque_number = row.cheque_number
				receipt.cheque_date = row.cheque_date
				receipt.bank_name = row.bank_name
				receipt.pdc_status = "Received"
				receipt.insert(ignore_permissions=True)
				# Link back to plan row
				frappe.db.set_value("Lease Contract PDC", row.name, "receipt", receipt.name)
				receipts_created.append(receipt.name)
	
	# Process Cash Plan
	if process_cash:
		for row in lease_contract.get("cash_plan_table", []):
			if row.receipt_date and row.amount:
				# Skip if receipt already exists for this row
				if row.receipt:
					continue
				receipt = frappe.new_doc("Lease Contract Receipt")
				receipt.lease_contract = lease_contract_name
				receipt.receipt_type = "Rent"
				receipt.payment_mode = "Cash"
				receipt.receipt_date = row.receipt_date
				receipt.amount = row.amount
				receipt.cash_receipt_number = row.receipt_number
				receipt.remarks = row.remarks
				receipt.insert(ignore_permissions=True)
				# Link back to plan row
				frappe.db.set_value("Lease Contract Cash Plan", row.name, "receipt", receipt.name)
				receipts_created.append(receipt.name)
	
	# Process Bank Transfer Plan
	if process_bank:
		for row in lease_contract.get("bank_transfer_plan_table", []):
			if row.transfer_date and row.amount and row.transaction_id:
				# Skip if receipt already exists for this row
				if row.receipt:
					continue
				receipt = frappe.new_doc("Lease Contract Receipt")
				receipt.lease_contract = lease_contract_name
				receipt.receipt_type = "Rent"
				receipt.payment_mode = "Bank Transfer"
				receipt.receipt_date = row.transfer_date
				receipt.amount = row.amount
				receipt.transaction_id = row.transaction_id
				receipt.bank_account = row.bank_account
				receipt.reference_number = row.reference_number
				receipt.attachment = row.remarks or "Bank Transfer Receipt"  # placeholder
				receipt.remarks = row.remarks
				receipt.insert(ignore_permissions=True)
				# Link back to plan row
				frappe.db.set_value("Lease Contract Bank Transfer Plan", row.name, "receipt", receipt.name)
				receipts_created.append(receipt.name)
	
	# Process Security Deposit Plan
	if process_sd:
		for row in lease_contract.get("security_deposit_plan_table", []):
			if row.amount and ((row.payment_mode == "Cheque" and row.cheque_number and row.cheque_date and row.cheque_copy) or
							   (row.payment_mode == "Cash") or
							   (row.payment_mode == "Bank Transfer" and row.transaction_id)):
				# Skip if receipt already exists for this row
				if row.receipt:
					continue
				receipt = frappe.new_doc("Lease Contract Receipt")
				receipt.lease_contract = lease_contract_name
				receipt.receipt_type = "Security Deposit"
				receipt.payment_mode = row.payment_mode
				receipt.receipt_date = today()
				receipt.amount = row.amount
				receipt.refund_status = "Held"
				
				if row.payment_mode == "Cheque":
					receipt.cheque_number = row.cheque_number
					receipt.cheque_date = row.cheque_date
					receipt.bank_name = row.bank_name
					receipt.attachment = row.cheque_copy
				elif row.payment_mode == "Cash":
					# receipt_number will be auto-generated in before_insert
					pass
				elif row.payment_mode == "Bank Transfer":
					receipt.transaction_id = row.transaction_id
					receipt.bank_account = row.bank_account
					receipt.reference_number = row.reference_number
					receipt.attachment = row.remarks or "Bank Transfer Receipt"
				
				receipt.insert(ignore_permissions=True)
				# Link back to plan row
				frappe.db.set_value("Lease Contract Security Deposit Plan", row.name, "receipt", receipt.name)
				receipts_created.append(receipt.name)
	
	return receipts_created