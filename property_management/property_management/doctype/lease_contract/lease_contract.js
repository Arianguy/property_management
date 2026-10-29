// Copyright (c) 2026, Savio Fernandes and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lease Contract", {
	refresh(frm) {
		// Add custom button to generate PDC rows
		if (frm.doc.payment_mode === "Cheque" || frm.doc.payment_mode === "Mixed") {
			frm.add_custom_button(__("Generate PDC Rows"), () => {
				frm.call("generate_pdc_rows").then(() => {
					frm.refresh_field("pdcs_table");
				});
			}, __("Actions"));
		}

		// Show/hide PDC section based on payment mode
		frm.toggle_display("pdcs_table", ["Cheque", "Mixed"].includes(frm.doc.payment_mode));
		frm.toggle_display("number_of_pdcs", ["Cheque", "Mixed"].includes(frm.doc.payment_mode));
		frm.toggle_display("column_break_pdc", ["Cheque", "Mixed"].includes(frm.doc.payment_mode));
	},

	payment_mode(frm) {
		const show_pdc = ["Cheque", "Mixed"].includes(frm.doc.payment_mode);
		frm.toggle_display("pdcs_table", show_pdc);
		frm.toggle_display("number_of_pdcs", show_pdc);
		frm.toggle_display("column_break_pdc", show_pdc);
		frm.toggle_reqd("number_of_pdcs", show_pdc);

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
	}
});

// Child table validation
frappe.ui.form.on("Lease Contract PDC", {
	amount(frm, cdt, cdn) {
		validate_total_pdc_amount(frm);
	},

	pdcs_table_remove(frm) {
		validate_total_pdc_amount(frm);
	}
});

function validate_total_pdc_amount(frm) {
	if (!frm.doc.contract_value) return;

	let total = 0;
	(frm.doc.pdcs_table || []).forEach(row => {
		total += flt(row.amount);
	});

	if (total !== flt(frm.doc.contract_value)) {
		frappe.msgprint({
			title: __("Amount Mismatch"),
			message: __("Total PDC amount ({0}) must equal Contract Value ({1})", [total, frm.doc.contract_value]),
			indicator: "orange"
		});
	}
}