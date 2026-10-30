// Copyright (c) 2026, Savio Fernandes and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lease Contract", {
	refresh(frm) {
		// Show/hide sections based on payment mode
		frm.toggle_display("pdcs_table", ["Cheque", "Mixed"].includes(frm.doc.payment_mode));
		frm.toggle_display("number_of_pdcs", ["Cheque", "Mixed"].includes(frm.doc.payment_mode));
		
		frm.toggle_display("cash_plan_section", ["Cash", "Mixed"].includes(frm.doc.payment_mode));
		frm.toggle_display("cash_plan_table", ["Cash", "Mixed"].includes(frm.doc.payment_mode));
		
		frm.toggle_display("bank_transfer_plan_section", ["Bank Transfer", "Mixed"].includes(frm.doc.payment_mode));
		frm.toggle_display("bank_transfer_plan_table", ["Bank Transfer", "Mixed"].includes(frm.doc.payment_mode));
		
		frm.toggle_display("security_deposit_plan_section", frm.doc.security_deposit > 0);
		frm.toggle_display("security_deposit_plan_table", frm.doc.security_deposit > 0);
		frm.toggle_display("security_deposit_mode", frm.doc.security_deposit > 0);
	},

	payment_mode(frm) {
		const show_pdc = ["Cheque", "Mixed"].includes(frm.doc.payment_mode);
		const show_cash = ["Cash", "Mixed"].includes(frm.doc.payment_mode);
		const show_bank = ["Bank Transfer", "Mixed"].includes(frm.doc.payment_mode);
		
		frm.toggle_display("pdcs_table", show_pdc);
		frm.toggle_display("number_of_pdcs", show_pdc);
		frm.toggle_reqd("number_of_pdcs", show_pdc);
		
		frm.toggle_display("cash_plan_section", show_cash);
		frm.toggle_display("cash_plan_table", show_cash);
		
		frm.toggle_display("bank_transfer_plan_section", show_bank);
		frm.toggle_display("bank_transfer_plan_table", show_bank);

		if (show_pdc && !frm.doc.number_of_pdcs) {
			frm.set_value("number_of_pdcs", 1);
		}
	},

	number_of_pdcs(frm) {
		if (frm.doc.number_of_pdcs && frm.doc.contract_value) {
			frm.call("generate_pdc_rows").then(() => {
				frm.refresh_field("pdcs_table");
			});
		}
	},

	contract_value(frm) {
		// Recalculate PDC amounts when contract value changes
		if (frm.doc.number_of_pdcs && frm.doc.pdcs_table?.length) {
			frm.call("generate_pdc_rows").then(() => {
				frm.refresh_field("pdcs_table");
			});
		}
	},

	security_deposit(frm) {
		frm.toggle_display("security_deposit_mode", frm.doc.security_deposit > 0);
		frm.toggle_display("security_deposit_plan_section", frm.doc.security_deposit > 0);
		frm.toggle_display("security_deposit_plan_table", frm.doc.security_deposit > 0);
	},

	security_deposit_mode(frm) {
		if (frm.doc.security_deposit_mode && frm.doc.security_deposit) {
			// Auto-generate security deposit plan row based on mode
			frm.call("generate_security_deposit_row").then(() => {
				frm.refresh_field("security_deposit_plan_table");
			});
		}
	}
});

// Child table validation for PDC
frappe.ui.form.on("Lease Contract PDC", {
	amount(frm, cdt, cdn) {
		validate_total_pdc_amount(frm);
	},

	cheque_copy(frm, cdt, cdn) {
		validate_total_pdc_amount(frm);
	},

	pdcs_table_remove(frm) {
		validate_total_pdc_amount(frm);
	}
});

// Cash Plan validation
frappe.ui.form.on("Lease Contract Cash Plan", {
	amount(frm, cdt, cdn) {
		validate_cash_plan_total(frm);
	},
	cash_plan_table_remove(frm) {
		validate_cash_plan_total(frm);
	}
});

// Bank Transfer Plan validation
frappe.ui.form.on("Lease Contract Bank Transfer Plan", {
	amount(frm, cdt, cdn) {
		validate_bank_plan_total(frm);
	},
	bank_transfer_plan_table_remove(frm) {
		validate_bank_plan_total(frm);
	}
});

// Security Deposit Plan validation
frappe.ui.form.on("Lease Contract Security Deposit Plan", {
	amount(frm, cdt, cdn) {
		validate_sd_plan_total(frm);
	},
	security_deposit_plan_table_remove(frm) {
		validate_sd_plan_total(frm);
	},
	// Auto-set payment_mode from parent when row is added
	form_render(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row && !row.payment_mode && frm.doc.security_deposit_mode) {
			frappe.model.set_value(cdt, cdn, "payment_mode", frm.doc.security_deposit_mode);
		}
	}
});

function validate_total_pdc_amount(frm) {
	if (!frm.doc.contract_value) return;

	let total = 0;
	let has_missing_copy = false;
	(frm.doc.pdcs_table || []).forEach(row => {
		total += flt(row.amount);
		if (!row.cheque_copy) {
			has_missing_copy = true;
		}
	});

	if (total !== flt(frm.doc.contract_value)) {
		frappe.msgprint({
			title: __("Amount Mismatch"),
			message: __("Total PDC amount ({0}) must equal Contract Value ({1})", [total, frm.doc.contract_value]),
			indicator: "orange"
		});
	}
	
	if (has_missing_copy) {
		frm.dashboard.add_indicator(__("Some PDC rows are missing Cheque Copy attachment"), "orange");
	}
}

function validate_cash_plan_total(frm) {
	if (!frm.doc.contract_value || frm.doc.payment_mode !== "Cash") return;

	let total = 0;
	(frm.doc.cash_plan_table || []).forEach(row => {
		total += flt(row.amount);
	});

	if (total !== flt(frm.doc.contract_value)) {
		frappe.msgprint({
			title: __("Amount Mismatch"),
			message: __("Total Cash Plan amount ({0}) must equal Contract Value ({1})", [total, frm.doc.contract_value]),
			indicator: "orange"
		});
	}
}

function validate_bank_plan_total(frm) {
	if (!frm.doc.contract_value || frm.doc.payment_mode !== "Bank Transfer") return;

	let total = 0;
	(frm.doc.bank_transfer_plan_table || []).forEach(row => {
		total += flt(row.amount);
	});

	if (total !== flt(frm.doc.contract_value)) {
		frappe.msgprint({
			title: __("Amount Mismatch"),
			message: __("Total Bank Transfer Plan amount ({0}) must equal Contract Value ({1})", [total, frm.doc.contract_value]),
			indicator: "orange"
		});
	}
}

function validate_sd_plan_total(frm) {
	if (!frm.doc.security_deposit) return;

	let total = 0;
	(frm.doc.security_deposit_plan_table || []).forEach(row => {
		total += flt(row.amount);
	});

	if (total !== flt(frm.doc.security_deposit)) {
		frappe.msgprint({
			title: __("Amount Mismatch"),
			message: __("Total Security Deposit Plan amount ({0}) must equal Security Deposit ({1})", [total, frm.doc.security_deposit]),
			indicator: "orange"
		});
	}
}