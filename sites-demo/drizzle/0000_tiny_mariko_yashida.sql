CREATE TABLE `approvals` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`payload_json` text NOT NULL,
	`submitted_by` text NOT NULL,
	`status` text NOT NULL,
	`reviewer` text,
	`note` text,
	`created_at` text NOT NULL,
	`reviewed_at` text,
	`review_token` text,
	CONSTRAINT "approvals_kind_check" CHECK("approvals"."kind" IN ('rate', 'po')),
	CONSTRAINT "approvals_status_check" CHECK("approvals"."status" IN ('pending', 'approved', 'rejected'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `approvals_review_token_unique` ON `approvals` (`review_token`);--> statement-breakpoint
CREATE INDEX `approvals_status_idx` ON `approvals` (`status`);--> statement-breakpoint
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
	FOREIGN KEY (`translator_id`) REFERENCES `translators`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "purchase_orders_status_check" CHECK("purchase_orders"."status" IN ('draft', 'confirmed', 'paid')),
	CONSTRAINT "purchase_orders_word_count_check" CHECK("purchase_orders"."word_count" BETWEEN 0 AND 100000000),
	CONSTRAINT "purchase_orders_rate_check" CHECK("purchase_orders"."unit_rate_micros" BETWEEN 0 AND 100000000),
	CONSTRAINT "purchase_orders_amount_check" CHECK("purchase_orders"."amount_cents" >= 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `purchase_orders_po_number_unique` ON `purchase_orders` (`po_number`);--> statement-breakpoint
CREATE INDEX `purchase_orders_status_idx` ON `purchase_orders` (`status`);--> statement-breakpoint
CREATE TABLE `rates` (
	`id` text PRIMARY KEY NOT NULL,
	`translator_id` text NOT NULL,
	`language_pair` text NOT NULL,
	`rate_micros` integer NOT NULL,
	`currency` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`translator_id`) REFERENCES `translators`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "rates_rate_micros_check" CHECK("rates"."rate_micros" BETWEEN 0 AND 100000000)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `rates_translator_pair_idx` ON `rates` (`translator_id`,`language_pair`);--> statement-breakpoint
CREATE TABLE `translators` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`email` text NOT NULL,
	`native_language` text NOT NULL,
	`status` text NOT NULL,
	`onboarded_at` text NOT NULL,
	CONSTRAINT "translators_status_check" CHECK("translators"."status" IN ('active', 'inactive'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `translators_email_unique` ON `translators` (`email`);