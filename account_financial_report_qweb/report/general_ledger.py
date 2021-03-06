# -*- coding: utf-8 -*-
# © 2016 Julien Coux (Camptocamp)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import models, fields, api, _


class GeneralLedgerReport(models.TransientModel):
    """ Here, we just define class fields.
    For methods, go more bottom at this file.

    The class hierarchy is :
    * GeneralLedgerReport
    ** GeneralLedgerReportAccount
    *** GeneralLedgerReportMoveLine
            For non receivable/payable accounts
            For receivable/payable centralized accounts
    *** GeneralLedgerReportPartner
            For receivable/payable and not centralized accounts
    **** GeneralLedgerReportMoveLine
            For receivable/payable and not centralized accounts
    """

    _name = 'report_general_ledger_qweb'

    # Filters fields, used for data computation
    date_from = fields.Date()
    date_to = fields.Date()
    fy_start_date = fields.Date()
    only_posted_moves = fields.Boolean()
    hide_account_balance_at_0 = fields.Boolean()
    company_id = fields.Many2one(comodel_name='res.company')
    filter_account_ids = fields.Many2many(comodel_name='account.account')
    filter_partner_ids = fields.Many2many(comodel_name='res.partner')
    filter_cost_center_ids = fields.Many2many(
        comodel_name='account.analytic.account'
    )
    centralize = fields.Boolean()

    # Flag fields, used for report display
    has_second_currency = fields.Boolean()
    show_cost_center = fields.Boolean(
        default=lambda self: self.env.user.has_group(
            'analytic.group_analytic_accounting'
        )
    )

    # Data fields, used to browse report data
    account_ids = fields.One2many(
        comodel_name='report_general_ledger_qweb_account',
        inverse_name='report_id'
    )

    # Compute of unaffected earnings account
    @api.depends('company_id')
    def _compute_unaffected_earnings_account(self):
        account_type = self.env.ref('account.data_unaffected_earnings')
        self.unaffected_earnings_account = self.env['account.account'].search(
            [
                ('user_type_id', '=', account_type.id),
                ('company_id', '=', self.company_id.id)
            ])

    unaffected_earnings_account = fields.Many2one(
        comodel_name='account.account',
        compute='_compute_unaffected_earnings_account',
        store=True
    )


class GeneralLedgerReportAccount(models.TransientModel):

    _name = 'report_general_ledger_qweb_account'
    _order = 'code ASC'

    report_id = fields.Many2one(
        comodel_name='report_general_ledger_qweb',
        ondelete='cascade',
        index=True
    )

    # Data fields, used to keep link with real object
    account_id = fields.Many2one(
        'account.account',
        index=True
    )

    # Data fields, used for report display
    code = fields.Char()
    name = fields.Char()
    initial_debit = fields.Float(digits=(16, 2))
    initial_credit = fields.Float(digits=(16, 2))
    initial_balance = fields.Float(digits=(16, 2))
    final_debit = fields.Float(digits=(16, 2))
    final_credit = fields.Float(digits=(16, 2))
    final_balance = fields.Float(digits=(16, 2))

    # Flag fields, used for report display and for data computation
    is_partner_account = fields.Boolean()

    # Data fields, used to browse report data
    move_line_ids = fields.One2many(
        comodel_name='report_general_ledger_qweb_move_line',
        inverse_name='report_account_id'
    )
    partner_ids = fields.One2many(
        comodel_name='report_general_ledger_qweb_partner',
        inverse_name='report_account_id'
    )


class GeneralLedgerReportPartner(models.TransientModel):

    _name = 'report_general_ledger_qweb_partner'

    report_account_id = fields.Many2one(
        comodel_name='report_general_ledger_qweb_account',
        ondelete='cascade',
        index=True
    )

    # Data fields, used to keep link with real object
    partner_id = fields.Many2one(
        'res.partner',
        index=True
    )

    # Data fields, used for report display
    name = fields.Char()
    initial_debit = fields.Float(digits=(16, 2))
    initial_credit = fields.Float(digits=(16, 2))
    initial_balance = fields.Float(digits=(16, 2))
    final_debit = fields.Float(digits=(16, 2))
    final_credit = fields.Float(digits=(16, 2))
    final_balance = fields.Float(digits=(16, 2))

    # Data fields, used to browse report data
    move_line_ids = fields.One2many(
        comodel_name='report_general_ledger_qweb_move_line',
        inverse_name='report_partner_id'
    )

    @api.model
    def _generate_order_by(self, order_spec, query):
        """Custom order to display "No partner allocated" at last position."""
        return """
ORDER BY
    CASE
        WHEN "report_general_ledger_qweb_partner"."partner_id" IS NOT NULL
        THEN 0
        ELSE 1
    END,
    "report_general_ledger_qweb_partner"."name"
        """


class GeneralLedgerReportMoveLine(models.TransientModel):

    _name = 'report_general_ledger_qweb_move_line'

    report_account_id = fields.Many2one(
        comodel_name='report_general_ledger_qweb_account',
        ondelete='cascade',
        index=True
    )
    report_partner_id = fields.Many2one(
        comodel_name='report_general_ledger_qweb_partner',
        ondelete='cascade',
        index=True
    )

    # Data fields, used to keep link with real object
    move_line_id = fields.Many2one('account.move.line')

    # Data fields, used for report display
    date = fields.Date()
    entry = fields.Char()
    journal = fields.Char()
    account = fields.Char()
    partner = fields.Char()
    label = fields.Char()
    cost_center = fields.Char()
    matching_number = fields.Char()
    debit = fields.Float(digits=(16, 2))
    credit = fields.Float(digits=(16, 2))
    cumul_balance = fields.Float(digits=(16, 2))
    currency_name = fields.Char()
    amount_currency = fields.Float(digits=(16, 2))


class GeneralLedgerReportCompute(models.TransientModel):
    """ Here, we just define methods.
    For class fields, go more top at this file.
    """

    _inherit = 'report_general_ledger_qweb'

    @api.multi
    def print_report(self, xlsx_report=False):
        self.ensure_one()
        self.compute_data_for_report()
        if xlsx_report:
            report_name = 'account_financial_report_qweb.' \
                          'report_general_ledger_xlsx'
        else:
            report_name = 'account_financial_report_qweb.' \
                          'report_general_ledger_qweb'
        return self.env['report'].get_action(records=self,
                                             report_name=report_name)

    @api.multi
    def compute_data_for_report(self):
        self.ensure_one()
        # Compute report data
        self._inject_account_values()
        self._inject_partner_values()

        # Add unaffected earnings account
        if (not self.filter_account_ids or
                self.unaffected_earnings_account.id in
                self.filter_account_ids.ids):
            self._inject_unaffected_earnings_account_values()

        self._inject_line_not_centralized_values()
        self._inject_line_not_centralized_values(is_account_line=False,
                                                 is_partner_line=True)
        self._inject_line_not_centralized_values(is_account_line=False,
                                                 is_partner_line=True,
                                                 only_empty_partner_line=True)
        if self.centralize:
            self._inject_line_centralized_values()

        # Complete unaffected earnings account
        if (not self.filter_account_ids or
                self.unaffected_earnings_account.id in
                self.filter_account_ids.ids):
            self._complete_unaffected_earnings_account_values()

        # Compute display flag
        self._compute_has_second_currency()
        # Refresh cache because all data are computed with SQL requests
        self.refresh()

    def _inject_account_values(self):
        """Inject report values for report_general_ledger_qweb_account."""
        subquery_sum_amounts = """
        SELECT
            a.id AS account_id,
            SUM(ml.debit) AS debit,
            SUM(ml.credit) AS credit,
            SUM(ml.balance) AS balance
        FROM
            accounts a
        INNER JOIN
            account_account_type at ON a.user_type_id = at.id
        INNER JOIN
            account_move_line ml
                ON a.id = ml.account_id
                AND ml.date <= %s
                AND
                    (
                        at.include_initial_balance != TRUE AND ml.date >= %s
                        OR at.include_initial_balance = TRUE
                    )
        """
        if self.only_posted_moves:
            subquery_sum_amounts += """
        INNER JOIN
            account_move m ON ml.move_id = m.id AND m.state = 'posted'
            """
        if self.filter_cost_center_ids:
            subquery_sum_amounts += """
        INNER JOIN
            account_analytic_account aa
                ON
                    ml.analytic_account_id = aa.id
                    AND aa.id IN %s
            """
        subquery_sum_amounts += """
        GROUP BY
            a.id
        """
        query_inject_account = """
WITH
    accounts AS
        (
            SELECT
                a.id,
                a.code,
                a.name,
                a.internal_type IN ('payable', 'receivable')
                    AS is_partner_account,
                a.user_type_id
            FROM
                account_account a
            """
        if self.filter_partner_ids or self.filter_cost_center_ids:
            query_inject_account += """
            INNER JOIN
                account_move_line ml ON a.id = ml.account_id
            """
        if self.filter_partner_ids:
            query_inject_account += """
            INNER JOIN
                res_partner p ON ml.partner_id = p.id
            """
        if self.filter_cost_center_ids:
            query_inject_account += """
            INNER JOIN
                account_analytic_account aa
                    ON
                        ml.analytic_account_id = aa.id
                        AND aa.id IN %s
            """
        query_inject_account += """
            WHERE
                a.company_id = %s
            AND a.id != %s
                    """
        if self.filter_account_ids:
            query_inject_account += """
            AND
                a.id IN %s
            """
        if self.filter_partner_ids:
            query_inject_account += """
            AND
                p.id IN %s
            """
        if self.filter_partner_ids or self.filter_cost_center_ids:
            query_inject_account += """
            GROUP BY
                a.id
            """
        query_inject_account += """
        ),
    initial_sum_amounts AS ( """ + subquery_sum_amounts + """ ),
    final_sum_amounts AS ( """ + subquery_sum_amounts + """ )
INSERT INTO
    report_general_ledger_qweb_account
    (
    report_id,
    create_uid,
    create_date,
    account_id,
    code,
    name,
    initial_debit,
    initial_credit,
    initial_balance,
    final_debit,
    final_credit,
    final_balance,
    is_partner_account
    )
SELECT
    %s AS report_id,
    %s AS create_uid,
    NOW() AS create_date,
    a.id AS account_id,
    a.code,
    a.name,
    COALESCE(i.debit, 0.0) AS initial_debit,
    COALESCE(i.credit, 0.0) AS initial_credit,
    COALESCE(i.balance, 0.0) AS initial_balance,
    COALESCE(f.debit, 0.0) AS final_debit,
    COALESCE(f.credit, 0.0) AS final_credit,
    COALESCE(f.balance, 0.0) AS final_balance,
    a.is_partner_account
FROM
    accounts a
LEFT JOIN
    initial_sum_amounts i ON a.id = i.account_id
LEFT JOIN
    final_sum_amounts f ON a.id = f.account_id
WHERE
    (
        i.debit IS NOT NULL AND i.debit != 0
        OR i.credit IS NOT NULL AND i.credit != 0
        OR i.balance IS NOT NULL AND i.balance != 0
        OR f.debit IS NOT NULL AND f.debit != 0
        OR f.credit IS NOT NULL AND f.credit != 0
        OR f.balance IS NOT NULL AND f.balance != 0
    )
        """
        if self.hide_account_balance_at_0:
            query_inject_account += """
AND
    f.balance IS NOT NULL AND f.balance != 0
            """
        query_inject_account_params = ()
        if self.filter_cost_center_ids:
            query_inject_account_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_account_params += (
            self.company_id.id,
            self.unaffected_earnings_account.id,
        )
        if self.filter_account_ids:
            query_inject_account_params += (
                tuple(self.filter_account_ids.ids),
            )
        if self.filter_partner_ids:
            query_inject_account_params += (
                tuple(self.filter_partner_ids.ids),
            )
        query_inject_account_params += (
            self.date_from,
            self.fy_start_date,
        )
        if self.filter_cost_center_ids:
            query_inject_account_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_account_params += (
            self.date_to,
            self.fy_start_date,
        )
        if self.filter_cost_center_ids:
            query_inject_account_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_account_params += (
            self.id,
            self.env.uid,
        )
        self.env.cr.execute(query_inject_account, query_inject_account_params)

    def _inject_partner_values(self):
        """ Inject report values for report_general_ledger_qweb_partner.

        Only for "partner" accounts (payable and receivable).
        """
        subquery_sum_amounts = """
            SELECT
                ap.account_id AS account_id,
                ap.partner_id AS partner_id,
                SUM(ml.debit) AS debit,
                SUM(ml.credit) AS credit,
                SUM(ml.balance) AS balance
            FROM
                accounts_partners ap
            INNER JOIN
                account_move_line ml
                    ON ap.account_id = ml.account_id
                    AND (
                        ap.partner_id = ml.partner_id
                        OR ap.partner_id IS NULL AND ml.partner_id IS NULL
                        )
                    AND ml.date <= %s
                    AND (
                        ap.include_initial_balance != TRUE AND ml.date >= %s
                        OR ap.include_initial_balance = TRUE
                        )
        """
        if self.only_posted_moves:
            subquery_sum_amounts += """
            INNER JOIN
                account_move m ON ml.move_id = m.id AND m.state = 'posted'
            """
        if self.filter_cost_center_ids:
            subquery_sum_amounts += """
        INNER JOIN
            account_analytic_account aa
                ON
                    ml.analytic_account_id = aa.id
                    AND aa.id IN %s
            """
        subquery_sum_amounts += """
            GROUP BY
                ap.account_id, ap.partner_id
        """
        query_inject_partner = """
WITH
    accounts_partners AS
        (
            SELECT
                ra.id AS report_account_id,
                a.id AS account_id,
                at.include_initial_balance AS include_initial_balance,
                p.id AS partner_id,
                COALESCE(
                    CASE
                        WHEN
                            NULLIF(p.name, '') IS NOT NULL
                            AND NULLIF(p.ref, '') IS NOT NULL
                        THEN p.name || ' (' || p.ref || ')'
                        ELSE p.name
                    END,
                    '""" + _('No partner allocated') + """'
                ) AS partner_name
            FROM
                report_general_ledger_qweb_account ra
            INNER JOIN
                account_account a ON ra.account_id = a.id
            INNER JOIN
                account_account_type at ON a.user_type_id = at.id
            INNER JOIN
                account_move_line ml ON a.id = ml.account_id
            LEFT JOIN
                res_partner p ON ml.partner_id = p.id
                    """
        if self.filter_cost_center_ids:
            query_inject_partner += """
            INNER JOIN
                account_analytic_account aa
                    ON
                        ml.analytic_account_id = aa.id
                        AND aa.id IN %s
            """
        query_inject_partner += """
            WHERE
                ra.report_id = %s
            AND
                ra.is_partner_account = TRUE
                        """
        if self.centralize:
            query_inject_partner += """
            AND
                (a.centralized IS NULL OR a.centralized != TRUE)
                    """
        if self.filter_partner_ids:
            query_inject_partner += """
            AND
                p.id IN %s
            """
        query_inject_partner += """
            GROUP BY
                ra.id,
                a.id,
                p.id,
                at.include_initial_balance
        ),
    initial_sum_amounts AS ( """ + subquery_sum_amounts + """ ),
    final_sum_amounts AS ( """ + subquery_sum_amounts + """ )
INSERT INTO
    report_general_ledger_qweb_partner
    (
    report_account_id,
    create_uid,
    create_date,
    partner_id,
    name,
    initial_debit,
    initial_credit,
    initial_balance,
    final_debit,
    final_credit,
    final_balance
    )
SELECT
    ap.report_account_id,
    %s AS create_uid,
    NOW() AS create_date,
    ap.partner_id,
    ap.partner_name,
    COALESCE(i.debit, 0.0) AS initial_debit,
    COALESCE(i.credit, 0.0) AS initial_credit,
    COALESCE(i.balance, 0.0) AS initial_balance,
    COALESCE(f.debit, 0.0) AS final_debit,
    COALESCE(f.credit, 0.0) AS final_credit,
    COALESCE(f.balance, 0.0) AS final_balance
FROM
    accounts_partners ap
LEFT JOIN
    initial_sum_amounts i
        ON
            (
                ap.partner_id = i.partner_id
                OR ap.partner_id IS NULL AND i.partner_id IS NULL
            )
            AND ap.account_id = i.account_id
LEFT JOIN
    final_sum_amounts f
        ON
            (
                ap.partner_id = f.partner_id
                OR ap.partner_id IS NULL AND f.partner_id IS NULL
            )
            AND ap.account_id = f.account_id
WHERE
    (
        i.debit IS NOT NULL AND i.debit != 0
        OR i.credit IS NOT NULL AND i.credit != 0
        OR i.balance IS NOT NULL AND i.balance != 0
        OR f.debit IS NOT NULL AND f.debit != 0
        OR f.credit IS NOT NULL AND f.credit != 0
        OR f.balance IS NOT NULL AND f.balance != 0
    )
        """
        if self.hide_account_balance_at_0:
            query_inject_partner += """
AND
    f.balance IS NOT NULL AND f.balance != 0
            """
        query_inject_partner_params = ()
        if self.filter_cost_center_ids:
            query_inject_partner_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_partner_params += (
            self.id,
        )
        if self.filter_partner_ids:
            query_inject_partner_params += (
                tuple(self.filter_partner_ids.ids),
            )
        query_inject_partner_params += (
            self.date_from,
            self.fy_start_date,
        )
        if self.filter_cost_center_ids:
            query_inject_partner_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_partner_params += (
            self.date_to,
            self.fy_start_date,
        )
        if self.filter_cost_center_ids:
            query_inject_partner_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_partner_params += (
            self.env.uid,
        )
        self.env.cr.execute(query_inject_partner, query_inject_partner_params)

    def _inject_line_not_centralized_values(self,
                                            is_account_line=True,
                                            is_partner_line=False,
                                            only_empty_partner_line=False):
        """ Inject report values for report_general_ledger_qweb_move_line.

        If centralized option have been chosen,
        only non centralized accounts are computed.

        In function of `is_account_line` and `is_partner_line` values,
        the move_line link is made either with account or either with partner.

        The "only_empty_partner_line" value is used
        to compute data without partner.
        """
        query_inject_move_line = """
INSERT INTO
    report_general_ledger_qweb_move_line
    (
        """
        if is_account_line:
            query_inject_move_line += """
    report_account_id,
            """
        elif is_partner_line:
            query_inject_move_line += """
    report_partner_id,
            """
        query_inject_move_line += """
    create_uid,
    create_date,
    move_line_id,
    date,
    entry,
    journal,
    account,
    partner,
    label,
    cost_center,
    matching_number,
    debit,
    credit,
    cumul_balance,
    currency_name,
    amount_currency
    )
SELECT
        """
        if is_account_line:
            query_inject_move_line += """
    ra.id AS report_account_id,
            """
        elif is_partner_line:
            query_inject_move_line += """
    rp.id AS report_partner_id,
            """
        query_inject_move_line += """
    %s AS create_uid,
    NOW() AS create_date,
    ml.id AS move_line_id,
    ml.date,
    m.name AS entry,
    j.code AS journal,
    a.code AS account,
        """
        if not only_empty_partner_line:
            query_inject_move_line += """
    CASE
        WHEN
            NULLIF(p.name, '') IS NOT NULL
            AND NULLIF(p.ref, '') IS NOT NULL
        THEN p.name || ' (' || p.ref || ')'
        ELSE p.name
    END AS partner,
            """
        elif only_empty_partner_line:
            query_inject_move_line += """
    '""" + _('No partner allocated') + """' AS partner,
            """
        query_inject_move_line += """
    CONCAT_WS(' - ', NULLIF(ml.ref, ''), NULLIF(ml.name, '')) AS label,
    aa.name AS cost_center,
    fr.name AS matching_number,
    ml.debit,
    ml.credit,
        """
        if is_account_line:
            query_inject_move_line += """
    ra.initial_balance + (
        SUM(ml.balance)
        OVER (PARTITION BY a.code
              ORDER BY a.code, ml.date, ml.id)
    ) AS cumul_balance,
            """
        elif is_partner_line and not only_empty_partner_line:
            query_inject_move_line += """
    rp.initial_balance + (
        SUM(ml.balance)
        OVER (PARTITION BY a.code, p.name
              ORDER BY a.code, p.name, ml.date, ml.id)
    ) AS cumul_balance,
            """
        elif is_partner_line and only_empty_partner_line:
            query_inject_move_line += """
    rp.initial_balance + (
        SUM(ml.balance)
        OVER (PARTITION BY a.code
              ORDER BY a.code, ml.date, ml.id)
    ) AS cumul_balance,
            """
        query_inject_move_line += """
    c.name AS currency_name,
    ml.amount_currency
FROM
        """
        if is_account_line:
            query_inject_move_line += """
    report_general_ledger_qweb_account ra
            """
        elif is_partner_line:
            query_inject_move_line += """
    report_general_ledger_qweb_partner rp
INNER JOIN
    report_general_ledger_qweb_account ra ON rp.report_account_id = ra.id
            """
        query_inject_move_line += """
INNER JOIN
    account_move_line ml ON ra.account_id = ml.account_id
INNER JOIN
    account_move m ON ml.move_id = m.id
INNER JOIN
    account_journal j ON ml.journal_id = j.id
INNER JOIN
    account_account a ON ml.account_id = a.id
        """
        if is_account_line:
            query_inject_move_line += """
LEFT JOIN
    res_partner p ON ml.partner_id = p.id
            """
        elif is_partner_line and not only_empty_partner_line:
            query_inject_move_line += """
INNER JOIN
    res_partner p
        ON ml.partner_id = p.id AND rp.partner_id = p.id
            """
        query_inject_move_line += """
LEFT JOIN
    account_full_reconcile fr ON ml.full_reconcile_id = fr.id
LEFT JOIN
    res_currency c ON a.currency_id = c.id
                    """
        if self.filter_cost_center_ids:
            query_inject_move_line += """
INNER JOIN
    account_analytic_account aa
        ON
            ml.analytic_account_id = aa.id
            AND aa.id IN %s
            """
        else:
            query_inject_move_line += """
LEFT JOIN
    account_analytic_account aa ON ml.analytic_account_id = aa.id
            """
        query_inject_move_line += """
WHERE
    ra.report_id = %s
AND
        """
        if is_account_line:
            query_inject_move_line += """
    (ra.is_partner_account IS NULL OR ra.is_partner_account != TRUE)
            """
        elif is_partner_line:
            query_inject_move_line += """
    ra.is_partner_account = TRUE
            """
        if self.centralize:
            query_inject_move_line += """
AND
    (a.centralized IS NULL OR a.centralized != TRUE)
            """
        query_inject_move_line += """
AND
    ml.date BETWEEN %s AND %s
        """
        if self.only_posted_moves:
            query_inject_move_line += """
AND
    m.state = 'posted'
        """
        if only_empty_partner_line:
            query_inject_move_line += """
AND
    ml.partner_id IS NULL
AND
    rp.partner_id IS NULL
        """
        if is_account_line:
            query_inject_move_line += """
ORDER BY
    a.code, ml.date, ml.id
            """
        elif is_partner_line and not only_empty_partner_line:
            query_inject_move_line += """
ORDER BY
    a.code, p.name, ml.date, ml.id
            """
        elif is_partner_line and only_empty_partner_line:
            query_inject_move_line += """
ORDER BY
    a.code, ml.date, ml.id
            """

        query_inject_move_line_params = (
            self.env.uid,
        )
        if self.filter_cost_center_ids:
            query_inject_move_line_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_move_line_params += (
            self.id,
            self.date_from,
            self.date_to,
        )
        self.env.cr.execute(
            query_inject_move_line,
            query_inject_move_line_params
        )

    def _inject_line_centralized_values(self):
        """ Inject report values for report_general_ledger_qweb_move_line.

        Only centralized accounts are computed.
        """
        query_inject_move_line_centralized = """
WITH
    move_lines AS
        (
            SELECT
                ml.account_id,
                (
                    DATE_TRUNC('month', ml.date) + interval '1 month'
                                                 - interval '1 day'
                )::date AS date,
                SUM(ml.debit) AS debit,
                SUM(ml.credit) AS credit,
                SUM(ml.balance) AS balance
            FROM
                report_general_ledger_qweb_account ra
            INNER JOIN
                account_move_line ml ON ra.account_id = ml.account_id
            INNER JOIN
                account_move m ON ml.move_id = m.id
            INNER JOIN
                account_account a ON ml.account_id = a.id
        """
        if self.filter_cost_center_ids:
            query_inject_move_line_centralized += """
            INNER JOIN
                account_analytic_account aa
                    ON
                        ml.analytic_account_id = aa.id
                        AND aa.id IN %s
            """
        query_inject_move_line_centralized += """
            WHERE
                ra.report_id = %s
            AND
                a.centralized = TRUE
            AND
                ml.date BETWEEN %s AND %s
        """
        if self.only_posted_moves:
            query_inject_move_line_centralized += """
            AND
                m.state = 'posted'
            """
        query_inject_move_line_centralized += """
            GROUP BY
                ra.id, ml.account_id, a.code, 2
        )
INSERT INTO
    report_general_ledger_qweb_move_line
    (
    report_account_id,
    create_uid,
    create_date,
    date,
    account,
    label,
    debit,
    credit,
    cumul_balance
    )
SELECT
    ra.id AS report_account_id,
    %s AS create_uid,
    NOW() AS create_date,
    ml.date,
    a.code AS account,
    '""" + _('Centralized Entries') + """' AS label,
    ml.debit AS debit,
    ml.credit AS credit,
    ra.initial_balance + (
        SUM(ml.balance)
        OVER (PARTITION BY a.code ORDER BY ml.date)
    ) AS cumul_balance
FROM
    report_general_ledger_qweb_account ra
INNER JOIN
    move_lines ml ON ra.account_id = ml.account_id
INNER JOIN
    account_account a ON ml.account_id = a.id
LEFT JOIN
    res_currency c ON a.currency_id = c.id
WHERE
    ra.report_id = %s
AND
    (a.centralized IS NOT NULL AND a.centralized = TRUE)
ORDER BY
    a.code, ml.date
        """

        query_inject_move_line_centralized_params = ()
        if self.filter_cost_center_ids:
            query_inject_move_line_centralized_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_move_line_centralized_params += (
            self.id,
            self.date_from,
            self.date_to,
            self.env.uid,
            self.id,
        )
        self.env.cr.execute(
            query_inject_move_line_centralized,
            query_inject_move_line_centralized_params
        )

    def _compute_has_second_currency(self):
        """ Compute "has_second_currency" flag which will used for display."""
        query_update_has_second_currency = """
UPDATE
    report_general_ledger_qweb
SET
    has_second_currency =
        (
            SELECT
                TRUE
            FROM
                report_general_ledger_qweb_move_line l
            INNER JOIN
                report_general_ledger_qweb_account a
                    ON l.report_account_id = a.id
            WHERE
                a.report_id = %s
            AND l.currency_name IS NOT NULL
            LIMIT 1
        )
        OR
        (
            SELECT
                TRUE
            FROM
                report_general_ledger_qweb_move_line l
            INNER JOIN
                report_general_ledger_qweb_partner p
                    ON l.report_partner_id = p.id
            INNER JOIN
                report_general_ledger_qweb_account a
                    ON p.report_account_id = a.id
            WHERE
                a.report_id = %s
            AND l.currency_name IS NOT NULL
            LIMIT 1
        )
WHERE id = %s
        """
        params = (self.id,) * 3
        self.env.cr.execute(query_update_has_second_currency, params)

    def _inject_unaffected_earnings_account_values(self):
        """Inject the report values of the unaffected earnings account
        for report_general_ledger_qweb_account."""
        subquery_sum_amounts = """
        SELECT
            SUM(ml.balance) AS balance
        FROM
            account_account a
        INNER JOIN
            account_account_type at ON a.user_type_id = at.id
        INNER JOIN
            account_move_line ml
                ON a.id = ml.account_id
                AND ml.date <= %s
                AND
                    NOT(
                        at.include_initial_balance != TRUE AND ml.date >= %s
                        OR at.include_initial_balance = TRUE
                    )
        """
        if self.only_posted_moves:
            subquery_sum_amounts += """
        INNER JOIN
            account_move m ON ml.move_id = m.id AND m.state = 'posted'
            """
        if self.filter_cost_center_ids:
            subquery_sum_amounts += """
        INNER JOIN
            account_analytic_account aa
                ON
                    ml.analytic_account_id = aa.id
                    AND aa.id IN %s
            """
        subquery_sum_amounts += """
        WHERE
            a.company_id =%s
        AND a.id != %s
        """
        query_inject_account = """
        WITH
            initial_sum_amounts AS ( """ + subquery_sum_amounts + """ )
        INSERT INTO
            report_general_ledger_qweb_account
            (
            report_id,
            create_uid,
            create_date,
            account_id,
            code,
            name,
            is_partner_account,
            initial_balance
            )
        SELECT
            %s AS report_id,
            %s AS create_uid,
            NOW() AS create_date,
            a.id AS account_id,
            a.code,
            a.name,
            False AS is_partner_account,
            COALESCE(i.balance, 0.0) AS initial_balance
        FROM
            account_account a,
            initial_sum_amounts i
        WHERE
            a.company_id = %s
        AND a.id = %s
                """
        query_inject_account_params = (
            self.date_from,
            self.fy_start_date,
        )
        if self.filter_cost_center_ids:
            query_inject_account_params += (
                tuple(self.filter_cost_center_ids.ids),
            )
        query_inject_account_params += (
            self.company_id.id,
            self.unaffected_earnings_account.id,
            self.id,
            self.env.uid,
            self.company_id.id,
            self.unaffected_earnings_account.id,
        )
        self.env.cr.execute(query_inject_account,
                            query_inject_account_params)

    def _complete_unaffected_earnings_account_values(self):
        """Complete the report values of the unaffected earnings account
        for report_general_ledger_qweb_account."""
        query_update_unaffected_earnings_account_values = """
        WITH
            sum_amounts AS
                (
                    SELECT
                        SUM(COALESCE(rml.debit, 0.0)) AS debit,
                        SUM(COALESCE(rml.credit, 0.0)) AS credit,
                        SUM(
                            COALESCE(rml.debit, 0.0) -
                            COALESCE(rml.credit, 0.0)
                        ) + ra.initial_balance AS balance
                    FROM
                        report_general_ledger_qweb_account ra
                    LEFT JOIN
                        report_general_ledger_qweb_move_line rml
                            ON ra.id = rml.report_account_id
                    WHERE
                        ra.report_id = %s
                    AND ra.account_id = %s
                    GROUP BY
                        ra.id
                )
        UPDATE
            report_general_ledger_qweb_account ra
        SET
            initial_debit = 0.0,
            initial_credit = 0.0,
            final_debit = sum_amounts.debit,
            final_credit = sum_amounts.credit,
            final_balance = sum_amounts.balance
        FROM
            sum_amounts
        WHERE
            ra.report_id = %s
        AND ra.account_id = %s
        """
        params = (
            self.id,
            self.unaffected_earnings_account.id,
            self.id,
            self.unaffected_earnings_account.id,
        )
        self.env.cr.execute(
            query_update_unaffected_earnings_account_values,
            params
        )
