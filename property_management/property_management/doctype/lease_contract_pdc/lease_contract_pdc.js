// Copyright (c) 2026, Savio Fernandes and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lease Contract PDC", {
	refresh(frm) {
		// Show cleared_date only when status is Cleared
		frm.toggle_display("cleared_date", frm.doc.status === "Cleared");
	},

	status(frm) {
		frm.toggle_display("cleared_date", frm.doc.status === "Cleared");
		if (frm.doc.status === "Cleared" && !frm.doc.cleared_date) {
			frm.set_value("cleared_date", frappe.datetime.get_today());
		}
	}
});