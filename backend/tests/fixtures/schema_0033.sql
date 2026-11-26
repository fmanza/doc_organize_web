-- index ix_ai_usage_created_at
CREATE INDEX ix_ai_usage_created_at ON ai_usage (created_at);

-- index ix_ai_usage_project_created
CREATE INDEX ix_ai_usage_project_created ON ai_usage (project_id, created_at);

-- index ix_artifacts_run_id
CREATE INDEX ix_artifacts_run_id ON artifacts (run_id);

-- index ix_audit_log_action
CREATE INDEX ix_audit_log_action ON audit_log (action);

-- index ix_audit_log_tenant_id
CREATE INDEX ix_audit_log_tenant_id ON audit_log (tenant_id);

-- index ix_audit_log_ts
CREATE INDEX ix_audit_log_ts ON audit_log (ts);

-- index ix_context_document_axis_values_project_axis_slug
CREATE INDEX ix_context_document_axis_values_project_axis_slug ON context_document_axis_values (project_id, axis, slug);

-- index ix_context_documents_project_domain
CREATE INDEX ix_context_documents_project_domain ON context_documents (project_id, domain_slug, seq);

-- index ix_context_documents_project_key
CREATE INDEX ix_context_documents_project_key ON context_documents (project_id, document_key);

-- index ix_context_documents_project_language
CREATE INDEX ix_context_documents_project_language ON context_documents (project_id, language);

-- index ix_context_review_items_project_priority
CREATE INDEX ix_context_review_items_project_priority ON context_review_items (project_id, priority, id);

-- index ix_context_review_proposals_project_status
CREATE INDEX ix_context_review_proposals_project_status ON context_review_proposals (project_id, status, id);

-- index ix_duplicate_groups_run_reason_position
CREATE INDEX ix_duplicate_groups_run_reason_position ON duplicate_groups (run_id, reason, position);

-- index ix_locations_tenant_id
CREATE INDEX ix_locations_tenant_id ON locations (tenant_id);

-- index ix_project_manifest_versions_project_created
CREATE INDEX ix_project_manifest_versions_project_created ON project_manifest_versions (project_id, created_at);

-- index ix_project_members_user_id
CREATE INDEX ix_project_members_user_id ON project_members (user_id);

-- index ix_projects_destination_location_id
CREATE INDEX ix_projects_destination_location_id ON projects (destination_location_id);

-- index ix_projects_source_location_id
CREATE INDEX ix_projects_source_location_id ON projects (source_location_id);

-- index ix_projects_tenant_id
CREATE INDEX ix_projects_tenant_id ON projects (tenant_id);

-- index ix_roles_tenant_id
CREATE INDEX ix_roles_tenant_id ON roles (tenant_id);

-- index ix_runs_claim
CREATE INDEX ix_runs_claim ON runs (status, queue, created_at);

-- index ix_runs_project_created
CREATE INDEX ix_runs_project_created ON runs (project_id, created_at);

-- index ix_scan_errors_project_run
CREATE INDEX ix_scan_errors_project_run ON scan_errors (project_id, run_id);

-- index ix_scan_errors_run_id
CREATE INDEX ix_scan_errors_run_id ON scan_errors (run_id);

-- index ix_sessions_user_id
CREATE INDEX ix_sessions_user_id ON sessions (user_id);

-- index ix_taxonomy_templates_tenant_id
CREATE INDEX ix_taxonomy_templates_tenant_id ON taxonomy_templates (tenant_id);

-- index ix_users_role_id
CREATE INDEX ix_users_role_id ON users (role_id);

-- index ix_users_tenant_id
CREATE INDEX ix_users_tenant_id ON users (tenant_id);

-- index uq_runs_project_write
CREATE UNIQUE INDEX uq_runs_project_write ON runs (project_id) WHERE is_write AND status IN ('queued', 'running');

-- table ai_settings
CREATE TABLE ai_settings (
	family VARCHAR(64) NOT NULL,
	field VARCHAR(32) NOT NULL,
	value TEXT,
	ciphertext TEXT,
	updated_by INTEGER,
	updated_at DATETIME NOT NULL,
	CONSTRAINT ck_ai_settings_one_value CHECK ((value IS NULL) <> (ciphertext IS NULL)),
	CONSTRAINT fk_ai_settings_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT pk_ai_settings PRIMARY KEY (family, field)
);

-- table ai_usage
CREATE TABLE ai_usage (
	id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	tenant_id INTEGER,
	project_id INTEGER,
	project_name VARCHAR(128),
	run_id VARCHAR(36),
	operation VARCHAR(32) NOT NULL,
	task VARCHAR(32) NOT NULL,
	model VARCHAR(128),
	calls INTEGER DEFAULT '0' NOT NULL,
	cached INTEGER DEFAULT '0' NOT NULL,
	failed INTEGER DEFAULT '0' NOT NULL,
	prompt_tokens INTEGER DEFAULT '0' NOT NULL,
	completion_tokens INTEGER DEFAULT '0' NOT NULL,
	tokens_estimated BOOLEAN DEFAULT 0 NOT NULL,
	CONSTRAINT fk_ai_usage_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL,
	CONSTRAINT fk_ai_usage_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE SET NULL,
	CONSTRAINT fk_ai_usage_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE SET NULL,
	CONSTRAINT pk_ai_usage PRIMARY KEY (id),
	CONSTRAINT uq_ai_usage_run_task UNIQUE (run_id, task)
);

-- table alembic_version
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL,
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- table app_settings
CREATE TABLE app_settings (
	"key" VARCHAR(64) NOT NULL,
	value JSON NOT NULL,
	updated_by INTEGER,
	updated_at DATETIME NOT NULL,
	CONSTRAINT fk_app_settings_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT pk_app_settings PRIMARY KEY ("key")
);

-- table artifacts
CREATE TABLE artifacts (
	id INTEGER NOT NULL,
	run_id VARCHAR(36) NOT NULL,
	name VARCHAR(255) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	rel_path VARCHAR(1024) NOT NULL,
	size_bytes BIGINT NOT NULL,
	content_type VARCHAR(128) NOT NULL,
	created_by INTEGER,
	created_at DATETIME NOT NULL,
	CONSTRAINT ck_artifacts_kind CHECK (kind IN ('log', 'output', 'report')),
	CONSTRAINT fk_artifacts_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_artifacts_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE,
	CONSTRAINT pk_artifacts PRIMARY KEY (id)
);

-- table audit_log
CREATE TABLE audit_log (
	id INTEGER NOT NULL,
	tenant_id INTEGER NOT NULL,
	ts DATETIME NOT NULL,
	actor_user_id INTEGER,
	action VARCHAR(64) NOT NULL,
	outcome VARCHAR(16) NOT NULL,
	target_type VARCHAR(32),
	target_id VARCHAR(64),
	ip VARCHAR(64),
	details JSON,
	actor_name VARCHAR(64),
	CONSTRAINT fk_audit_log_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_audit_log_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	CONSTRAINT pk_audit_log PRIMARY KEY (id)
);

-- table context_document_axis_values
CREATE TABLE context_document_axis_values (
	project_id INTEGER NOT NULL,
	seq INTEGER NOT NULL,
	axis VARCHAR(41) NOT NULL,
	slug VARCHAR(128) NOT NULL,
	name VARCHAR(256) NOT NULL,
	confidence FLOAT,
	classified_by VARCHAR(8),
	evidence_verified BOOLEAN,
	evidence VARCHAR(500),
	CONSTRAINT fk_context_document_axis_values_document FOREIGN KEY(project_id, seq) REFERENCES context_documents (project_id, seq) ON DELETE CASCADE,
	CONSTRAINT pk_context_document_axis_values PRIMARY KEY (project_id, seq, axis, slug)
);

-- table context_documents
CREATE TABLE context_documents (
	project_id INTEGER NOT NULL,
	seq INTEGER NOT NULL,
	domain_slug VARCHAR(128),
	title VARCHAR(1024) NOT NULL,
	document_type VARCHAR(64),
	material_type VARCHAR(128),
	material_type_name VARCHAR(256),
	folder VARCHAR(4096) NOT NULL,
	path VARCHAR(4096) NOT NULL,
	organized_path VARCHAR(4096),
	failed BOOLEAN NOT NULL,
	collision BOOLEAN NOT NULL,
	classified_by VARCHAR(8),
	author VARCHAR(500),
	description TEXT,
	keywords JSON DEFAULT '[]' NOT NULL,
	language VARCHAR(8),
	ai_filled JSON DEFAULT '[]' NOT NULL,
	rules_domain VARCHAR(128),
	rules_confidence FLOAT,
	ai_domain VARCHAR(128),
	ai_confidence FLOAT,
	ai_reasoning VARCHAR(500),
	material_type_confidence FLOAT,
	unclassified_reason VARCHAR(32),
	document_key VARCHAR(4096),
	source_sha256 VARCHAR(64),
	version VARCHAR(64),
	version_group VARCHAR(4096),
	is_current BOOLEAN,
	CONSTRAINT fk_context_documents_project_id_project_contexts FOREIGN KEY(project_id) REFERENCES project_contexts (project_id) ON DELETE CASCADE,
	CONSTRAINT pk_context_documents PRIMARY KEY (project_id, seq)
);

-- table context_review_items
CREATE TABLE context_review_items (
	id INTEGER NOT NULL,
	project_id INTEGER NOT NULL,
	seq INTEGER,
	document_key VARCHAR(4096) NOT NULL,
	reason VARCHAR(32) NOT NULL,
	priority INTEGER NOT NULL,
	axis VARCHAR(41),
	value VARCHAR(128),
	confidence FLOAT,
	detail VARCHAR(1000),
	CONSTRAINT fk_context_review_items_project_id_project_contexts FOREIGN KEY(project_id) REFERENCES project_contexts (project_id) ON DELETE CASCADE,
	CONSTRAINT pk_context_review_items PRIMARY KEY (id)
);

-- table context_review_proposals
CREATE TABLE context_review_proposals (
	id INTEGER NOT NULL,
	project_id INTEGER NOT NULL,
	run_id VARCHAR(36),
	document_key VARCHAR(4096) NOT NULL,
	action VARCHAR(32) NOT NULL,
	axes JSON DEFAULT '{}' NOT NULL,
	rationale TEXT,
	evidence TEXT,
	source_sha256 VARCHAR(64),
	status VARCHAR(16) DEFAULT 'pending' NOT NULL,
	created_at DATETIME NOT NULL,
	decided_by INTEGER,
	decided_at DATETIME,
	decision_id VARCHAR(64),
	proposal_key VARCHAR(64),
	CONSTRAINT ck_context_review_proposals_status CHECK (status IN ('pending', 'accepted', 'discarded')),
	CONSTRAINT fk_context_review_proposals_decided_by_users FOREIGN KEY(decided_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_context_review_proposals_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT fk_context_review_proposals_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE SET NULL,
	CONSTRAINT pk_context_review_proposals PRIMARY KEY (id)
);

-- table duplicate_groups
CREATE TABLE "duplicate_groups" (
	run_id VARCHAR(36) NOT NULL,
	group_id VARCHAR(36) NOT NULL,
	reason VARCHAR(32) NOT NULL,
	position INTEGER NOT NULL,
	member_count INTEGER NOT NULL,
	members JSON NOT NULL,
	similarity FLOAT,
	lexical_similarity FLOAT,
	contained BOOLEAN DEFAULT 0 NOT NULL,
	CONSTRAINT fk_duplicate_groups_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE,
	CONSTRAINT pk_duplicate_groups PRIMARY KEY (run_id, group_id)
);

-- table locations
CREATE TABLE locations (
	id INTEGER NOT NULL,
	tenant_id INTEGER NOT NULL,
	name VARCHAR(128) NOT NULL,
	container_path VARCHAR(1024) NOT NULL,
	display_path VARCHAR(1024),
	kind VARCHAR(16) NOT NULL,
	usage VARCHAR(16) NOT NULL,
	access VARCHAR(8) NOT NULL,
	visibility VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	status_reasons JSON,
	latency_ms FLOAT,
	free_bytes BIGINT,
	writable BOOLEAN,
	probed_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	ignore_patterns JSON DEFAULT '[]' NOT NULL,
	CONSTRAINT ck_locations_access CHECK (access IN ('ro', 'rw')),
	CONSTRAINT ck_locations_kind CHECK (kind IN ('local', 'network')),
	CONSTRAINT ck_locations_status CHECK (status IN ('unknown', 'ok', 'degraded', 'unavailable')),
	CONSTRAINT ck_locations_usage CHECK (usage IN ('source', 'destination', 'both')),
	CONSTRAINT fk_locations_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	CONSTRAINT pk_locations PRIMARY KEY (id),
	CONSTRAINT uq_locations_container_path UNIQUE (container_path),
	CONSTRAINT uq_locations_tenant_name UNIQUE (tenant_id, name)
);

-- table periodic_tasks
CREATE TABLE periodic_tasks (
	name VARCHAR(64) NOT NULL,
	last_run_at DATETIME,
	claimed_by VARCHAR(128),
	CONSTRAINT pk_periodic_tasks PRIMARY KEY (name)
);

-- table project_contexts
CREATE TABLE "project_contexts" (
	project_id INTEGER NOT NULL,
	output_folder_name VARCHAR(255) NOT NULL,
	catalog_kind VARCHAR(16) NOT NULL,
	taxonomy_template_name VARCHAR(64),
	documents_count INTEGER NOT NULL,
	unclassified_count INTEGER NOT NULL,
	failed_count INTEGER NOT NULL,
	collisions_count INTEGER NOT NULL,
	site_built BOOLEAN NOT NULL,
	domains JSON NOT NULL,
	built_by_run_id VARCHAR(36),
	built_at DATETIME NOT NULL,
	ai_classification BOOLEAN DEFAULT 0 NOT NULL,
	built_with_version VARCHAR(128),
	ai_classification_model VARCHAR(128),
	ai_enrichment_model VARCHAR(128),
	taxonomy_axes JSON DEFAULT '[]' NOT NULL,
	ai_provenance JSON DEFAULT '[]' NOT NULL,
	freshness JSON,
	decisions_applied INTEGER DEFAULT '0' NOT NULL,
	stale_decisions JSON DEFAULT '[]' NOT NULL,
	orphan_decisions JSON DEFAULT '[]' NOT NULL,
	versions_mode VARCHAR(16),
	version_groups JSON DEFAULT '[]' NOT NULL,
	superseded JSON DEFAULT '[]' NOT NULL,
	superseded_count INTEGER DEFAULT '0' NOT NULL,
	versions_across_extensions BOOLEAN,
	CONSTRAINT fk_project_contexts_built_by_run_id_runs FOREIGN KEY(built_by_run_id) REFERENCES runs (id) ON DELETE SET NULL,
	CONSTRAINT fk_project_contexts_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT pk_project_contexts PRIMARY KEY (project_id)
);

-- table project_manifest_versions
CREATE TABLE project_manifest_versions (
	id INTEGER NOT NULL,
	project_id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	created_by INTEGER,
	action VARCHAR(16) NOT NULL,
	markdown TEXT,
	domains INTEGER,
	material_types INTEGER,
	CONSTRAINT ck_project_manifest_versions_action CHECK (action IN ('save', 'delete', 'restore', 'history_clear')),
	CONSTRAINT fk_project_manifest_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_project_manifest_versions_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT pk_project_manifest_versions PRIMARY KEY (id)
);

-- table project_members
CREATE TABLE project_members (
	project_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	role VARCHAR(16) NOT NULL,
	added_by INTEGER,
	added_at DATETIME NOT NULL,
	CONSTRAINT ck_project_members_role CHECK (role IN ('owner', 'editor', 'viewer')),
	CONSTRAINT fk_project_members_added_by_users FOREIGN KEY(added_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_project_members_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT fk_project_members_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT pk_project_members PRIMARY KEY (project_id, user_id)
);

-- table projects
CREATE TABLE "projects" (
	id INTEGER NOT NULL,
	tenant_id INTEGER NOT NULL,
	name VARCHAR(128) NOT NULL,
	description VARCHAR(1024),
	source_location_id INTEGER,
	source_subpaths JSON NOT NULL,
	destination_location_id INTEGER,
	destination_subpath VARCHAR(4096) NOT NULL,
	status VARCHAR(16) NOT NULL,
	created_by INTEGER,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	deleted_at DATETIME,
	capture_owner BOOLEAN DEFAULT 0 NOT NULL,
	ai_redact_credentials BOOLEAN DEFAULT 1 NOT NULL,
	context_versions VARCHAR(16) DEFAULT 'mark' NOT NULL,
	context_semantic BOOLEAN DEFAULT 0 NOT NULL,
	context_semantic_threshold FLOAT DEFAULT '0.75' NOT NULL,
	context_versions_across_extensions BOOLEAN DEFAULT 0 NOT NULL,
	excluded_paths JSON DEFAULT '[]' NOT NULL,
	ignore_patterns JSON DEFAULT '[]' NOT NULL,
	exclude_system_folders BOOLEAN DEFAULT 0 NOT NULL,
	CONSTRAINT ck_projects_context_versions CHECK (context_versions IN ('all', 'mark', 'current_only')),
	CONSTRAINT ck_projects_locations CHECK (status = 'deleted' OR (source_location_id IS NOT NULL AND destination_location_id IS NOT NULL)),
	CONSTRAINT ck_projects_status CHECK (status IN ('active', 'deleted')),
	CONSTRAINT fk_projects_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_projects_destination_location_id_locations FOREIGN KEY(destination_location_id) REFERENCES locations (id) ON DELETE RESTRICT,
	CONSTRAINT fk_projects_source_location_id_locations FOREIGN KEY(source_location_id) REFERENCES locations (id) ON DELETE RESTRICT,
	CONSTRAINT fk_projects_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	CONSTRAINT pk_projects PRIMARY KEY (id)
);

-- table roles
CREATE TABLE roles (
	id INTEGER NOT NULL,
	tenant_id INTEGER NOT NULL,
	name VARCHAR(64) NOT NULL,
	builtin VARCHAR(16),
	permissions JSON NOT NULL,
	created_by INTEGER,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	CONSTRAINT fk_roles_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	CONSTRAINT pk_roles PRIMARY KEY (id),
	CONSTRAINT uq_roles_tenant_name UNIQUE (tenant_id, name)
);

-- table run_events
CREATE TABLE run_events (
	run_id VARCHAR(36) NOT NULL,
	seq INTEGER NOT NULL,
	ts DATETIME NOT NULL,
	type VARCHAR(16) NOT NULL,
	data JSON NOT NULL,
	CONSTRAINT fk_run_events_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE,
	CONSTRAINT pk_run_events PRIMARY KEY (run_id, seq)
);

-- table runs
CREATE TABLE runs (
	id VARCHAR(36) NOT NULL,
	project_id INTEGER,
	operation VARCHAR(32) NOT NULL,
	queue VARCHAR(8) NOT NULL,
	status VARCHAR(16) NOT NULL,
	is_write BOOLEAN NOT NULL,
	params JSON NOT NULL,
	progress JSON,
	result JSON,
	error_code VARCHAR(64),
	error_message VARCHAR(1024),
	cancel_requested BOOLEAN NOT NULL,
	uninterruptible BOOLEAN NOT NULL,
	created_by INTEGER,
	worker_id VARCHAR(128),
	created_at DATETIME NOT NULL,
	started_at DATETIME,
	finished_at DATETIME,
	heartbeat_at DATETIME,
	workspace_purged_at DATETIME,
	cancel_reason VARCHAR(16),
	CONSTRAINT ck_runs_queue CHECK (queue IN ('cpu', 'gpu')),
	CONSTRAINT ck_runs_status CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
	CONSTRAINT fk_runs_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_runs_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT pk_runs PRIMARY KEY (id)
);

-- table scan_errors
CREATE TABLE scan_errors (
	id INTEGER NOT NULL,
	run_id VARCHAR(36) NOT NULL,
	project_id INTEGER NOT NULL,
	path VARCHAR(4096) NOT NULL,
	message VARCHAR(2000) NOT NULL,
	retry_count INTEGER NOT NULL,
	capped BOOLEAN NOT NULL,
	CONSTRAINT fk_scan_errors_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT fk_scan_errors_run_id_runs FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE,
	CONSTRAINT pk_scan_errors PRIMARY KEY (id)
);

-- table scanned_folders
CREATE TABLE scanned_folders (
	project_id INTEGER NOT NULL,
	subpath VARCHAR(4096) NOT NULL,
	used BOOLEAN NOT NULL,
	added_by INTEGER,
	added_at DATETIME NOT NULL,
	last_scanned_at DATETIME,
	last_run_id VARCHAR(36),
	excluded_subpaths JSON DEFAULT '[]' NOT NULL,
	CONSTRAINT fk_scanned_folders_added_by_users FOREIGN KEY(added_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_scanned_folders_last_run_id_runs FOREIGN KEY(last_run_id) REFERENCES runs (id) ON DELETE SET NULL,
	CONSTRAINT fk_scanned_folders_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE,
	CONSTRAINT pk_scanned_folders PRIMARY KEY (project_id, subpath)
);

-- table sessions
CREATE TABLE "sessions" (
	id INTEGER NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	last_seen_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	ip VARCHAR(64),
	user_agent VARCHAR(255),
	acting_tenant_id INTEGER,
	CONSTRAINT fk_sessions_acting_tenant_id_tenants FOREIGN KEY(acting_tenant_id) REFERENCES tenants (id) ON DELETE SET NULL,
	CONSTRAINT fk_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT pk_sessions PRIMARY KEY (id),
	CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash)
);

-- table taxonomy_templates
CREATE TABLE taxonomy_templates (
	id INTEGER NOT NULL,
	tenant_id INTEGER NOT NULL,
	name VARCHAR(64) NOT NULL,
	title VARCHAR(256),
	description VARCHAR(1024),
	markdown TEXT NOT NULL,
	created_by INTEGER,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	markdown_v1 TEXT,
	CONSTRAINT fk_taxonomy_templates_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
	CONSTRAINT fk_taxonomy_templates_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	CONSTRAINT pk_taxonomy_templates PRIMARY KEY (id),
	CONSTRAINT uq_taxonomy_templates_tenant_name UNIQUE (tenant_id, name)
);

-- table tenants
CREATE TABLE tenants (
	id INTEGER NOT NULL,
	slug VARCHAR(64) NOT NULL,
	name VARCHAR(128) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME DEFAULT '1970-01-01 00:00:00' NOT NULL,
	CONSTRAINT pk_tenants PRIMARY KEY (id),
	CONSTRAINT uq_tenants_slug UNIQUE (slug)
);

-- table users
CREATE TABLE "users" (
	id INTEGER NOT NULL,
	tenant_id INTEGER NOT NULL,
	username VARCHAR(64) NOT NULL,
	display_name VARCHAR(128) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	is_active BOOLEAN NOT NULL,
	failed_attempts INTEGER NOT NULL,
	locked_until DATETIME,
	password_changed_at DATETIME NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	role_id INTEGER NOT NULL,
	is_instance_admin BOOLEAN DEFAULT 0 NOT NULL,
	color_scheme VARCHAR(8) DEFAULT 'auto' NOT NULL,
	language VARCHAR(5) DEFAULT 'es' NOT NULL,
	CONSTRAINT fk_users_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id),
	CONSTRAINT fk_users_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id),
	CONSTRAINT pk_users PRIMARY KEY (id),
	CONSTRAINT uq_users_username UNIQUE (username)
);

-- table workers
CREATE TABLE workers (
	id VARCHAR(128) NOT NULL,
	queues JSON NOT NULL,
	version VARCHAR(32) NOT NULL,
	doc_organize_version VARCHAR(32),
	started_at DATETIME NOT NULL,
	heartbeat_at DATETIME NOT NULL,
	capabilities JSON,
	capabilities_at DATETIME,
	refresh_requested BOOLEAN NOT NULL,
	resources JSON,
	CONSTRAINT pk_workers PRIMARY KEY (id)
);

-- row alembic_version (version_num)
('0033')

-- row roles (id, tenant_id, name, builtin, permissions, created_by)
(1, 1, 'Administrador', 'admin', '["users.manage", "roles.manage", "audit.read", "templates.manage", "projects.create", "projects.all"]', None)

-- row roles (id, tenant_id, name, builtin, permissions, created_by)
(2, 1, 'Usuario', 'user', '["projects.create"]', None)

-- row tenants (id, slug, name)
(1, 'default', 'Predeterminado')
