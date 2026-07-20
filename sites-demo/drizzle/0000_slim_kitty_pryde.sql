CREATE TABLE `approvals` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`payload_json` text NOT NULL,
	`submitted_by` text NOT NULL,
	`status` text NOT NULL,
	`reviewer` text,
	`note` text,
	`created_at` text NOT NULL,
	`reviewed_at` text
);
--> statement-breakpoint
CREATE TABLE `purchase_orders` (
	`id` text PRIMARY KEY NOT NULL,
	`po_number` text NOT NULL,
	`translator_id` text NOT NULL,
	`month` text NOT NULL,
	`language_pair` text NOT NULL,
	`word_count` integer NOT NULL,
	`unit_rate_micros` integer NOT NULL,
	`amount_cents` integer NOT NULL,
	`currency` text NOT NULL,
	`status` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`translator_id`) REFERENCES `translators`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `purchase_orders_po_number_unique` ON `purchase_orders` (`po_number`);--> statement-breakpoint
CREATE TABLE `rates` (
	`id` text PRIMARY KEY NOT NULL,
	`translator_id` text NOT NULL,
	`language_pair` text NOT NULL,
	`rate_micros` integer NOT NULL,
	`currency` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`translator_id`) REFERENCES `translators`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `rates_translator_pair_idx` ON `rates` (`translator_id`,`language_pair`);--> statement-breakpoint
CREATE TABLE `translators` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`email` text NOT NULL,
	`native_language` text NOT NULL,
	`status` text NOT NULL,
	`onboarded_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `translators_email_unique` ON `translators` (`email`);