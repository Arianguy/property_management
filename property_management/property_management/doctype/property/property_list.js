frappe.listview_settings["Property"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const status = (doc.status || "").toUpperCase();

		if (status === "LEASED") {
			return [__("Leased"), "green", "status,=," + doc.status];
		}
		if (status === "VACANT") {
			return [__("Vacant"), "red", "status,=," + doc.status];
		}
				if (status === "SOLD" || status === "SOLD") {
			return [__("Sold"), "yellow", "status,=," + doc.status];
		}
		if (status === "MAINTAINANCE" || status === "MAINTENANCE") {
			return [__("Maintenance"), "orange", "status,=," + doc.status];
		}
	},
};
