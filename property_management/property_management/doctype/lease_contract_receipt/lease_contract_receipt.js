// Copyright (c) 2026, Savio Fernandes and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lease Contract Receipt", {
	refresh(frm) {
		if (frm.doc.payment_mode === "PDC") {
			// Add status action buttons
			if (frm.doc.docstatus === 1) {
				if (frm.doc.pdc_status === "Received") {
					frm.add_custom_button(__("Mark Deposited"), () => {
						frm.set_value("pdc_status", "Deposited");
						frm.set_value("deposited_date", frappe.datetime.get_today());
						frm.save();
					});
				}
				if (frm.doc.pdc_status === "Deposited") {
					frm.add_custom_button(__("Mark Cleared"), () => {
						frm.set_value("pdc_status", "Cleared");
						frm.set_value("cleared_date", frappe.datetime.get_today());
						frm.save();
					});
					frm.add_custom_button(__("Mark Bounced"), () => {
						frm.set_value("pdc_status", "Bounced");
						frm.set_value("bounced_date", frappe.datetime.get_today());
						frm.save();
					}, __("Actions"));
				}
				if (frm.doc.pdc_status === "Cleared") {
					frm.add_custom_button(__("View Payment Entry"), () => {
						if (frm.doc.clearing_entry) {
							frappe.set_route("Form", "Payment Entry", frm.doc.clearing_entry);
						}
					});
				}
				if (frm.doc.pdc_status === "Deposited" && frm.doc.deposit_entry) {
					frm.add_custom_button(__("View Deposit Entry"), () => {
						frappe.set_route("Form", "Journal Entry", frm.doc.deposit_entry);
					});
				}
			}
		}
		
		if (frm.doc.receipt_type === "Security Deposit" && frm.doc.docstatus === 1) {
			if (frm.doc.refund_status === "Held") {
				frm.add_custom_button(__("Refund Security Deposit"), () => {
					frappe.prompt([
						{"fieldname": "refund_amount", "fieldtype": "Currency", "label": "Refund Amount", "reqd": 1, "default": frm.doc.amount},
						{"fieldname": "refund_date", "fieldtype": "Date", "label": "Refund Date", "reqd": 1, "default": frappe.datetime.get_today()}
					], (values) => {
						frm.set_value("refund_status", "Fully Refunded");
						frm.set_value("refund_amount", values.refund_amount);
						frm.set_value("refund_date", values.refund_date);
						frm.save();
					});
				});
				
				frm.add_custom_button(__("Adjust Against Rent"), () => {
					frappe.prompt([
						{"fieldname": "adjust_amount", "fieldtype": "Currency", "label": "Adjustment Amount", "reqd": 1, "default": frm.doc.amount}
					], (values) => {
						frm.set_value("refund_status", "Adjusted");
						frm.set_value("refund_amount", values.adjust_amount);
						frm.save();
					});
				});
			}
		}
	},
	
	pdc_status(frm) {
		if (frm.doc.pdc_status === "Deposited" && !frm.doc.deposited_date) {
			frm.set_value("deposited_date", frappe.datetime.get_today());
		}
		if (frm.doc.pdc_status === "Cleared" && !frm.doc.cleared_date) {
			frm.set_value("cleared_date", frappe.datetime.get_today());
		}
		if (frm.doc.pdc_status === "Bounced" && !frm.doc.bounced_date) {
			frm.set_value("bounced_date", frappe.datetime.get_today());
		}
	},
	
	refund_status(frm) {
		if (frm.doc.refund_status === "Fully Refunded" && !frm.doc.refund_date) {
			frm.set_value("refund_date", frappe.datetime.get_today());
		}
	}
});