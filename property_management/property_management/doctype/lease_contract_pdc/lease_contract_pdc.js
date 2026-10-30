// Copyright (c) 2026, Savio Fernandes and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lease Contract PDC", {
	refresh(frm) {
		// Cheque copy is mandatory - show indicator
		if (!frm.doc.cheque_copy) {
			frm.dashboard.add_indicator(__("Cheque copy is required"), "orange");
		}
	}
});