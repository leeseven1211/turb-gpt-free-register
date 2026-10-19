# -*- coding: utf-8 -*-
import unittest

from core.account_search import AccountSearchError, account_search_filters, parse_account_search


class AccountSearchTests(unittest.TestCase):
    def test_shorthand_and_explicit_fields_have_the_same_meaning(self):
        for query in ("协议 jp", "协议/jp", "协议注册 / JP注册", "protocol 日本", "方式:协议 地区:JP", "方式：协议 地区： 日本"):
            with self.subTest(query=query):
                terms = parse_account_search(query)
                self.assertEqual([(term.field, term.value) for term in terms], [("method", "protocol"), ("region", "JP")])

    def test_browser_aliases_and_country_codes_are_case_insensitive(self):
        terms = parse_account_search("BROWSER uk")
        self.assertEqual([(term.field, term.value) for term in terms], [("method", "browser"), ("region", "GB")])
        self.assertEqual(parse_account_search("地区:IS")[0].value, "IS")

    def test_protocol_drivers_have_distinct_search_aliases(self):
        self.assertEqual(parse_account_search("开源协议")[0].value, "protocol_oss")
        self.assertEqual(parse_account_search("优化协议")[0].value, "protocol")
        self.assertEqual(parse_account_search("协议")[0].value, "protocol")

    def test_roxy_sources_have_distinct_search_aliases_and_display_labels(self):
        for query in ("roxy", "方式:roxy", "本地Roxy"):
            with self.subTest(query=query):
                terms = parse_account_search(query)
                self.assertEqual(terms[0].value, "roxy")
                self.assertEqual(account_search_filters(terms)[0]["display_value"], "本地 Roxy")
        for query in ("roxy_oss", "方式:roxy_oss", "开源Roxy"):
            with self.subTest(query=query):
                terms = parse_account_search(query)
                self.assertEqual(terms[0].value, "roxy_oss")
                self.assertEqual(account_search_filters(terms)[0]["display_value"], "开源 Roxy")

    def test_quoted_keywords_are_literal_and_keep_spaces_and_slashes(self):
        terms = parse_account_search('"协议" "jp" 备注:"a/b 待整理" 姓名:"Alice Smith"')
        self.assertEqual([(term.field, term.value) for term in terms], [
            ("text", "协议"), ("text", "jp"), ("note", "a/b 待整理"), ("name", "Alice Smith"),
        ])

    def test_scoped_values_do_not_become_method_or_country_filters(self):
        terms = parse_account_search("备注:jp 来源:protocol 邮箱:example.test ID:#123")
        self.assertEqual([(term.field, term.value) for term in terms], [
            ("note", "jp"), ("source", "protocol"), ("email", "example.test"), ("id", "123"),
        ])

    def test_removing_one_condition_preserves_quoted_literals(self):
        terms = parse_account_search('协议/jp 备注:"a/b 待整理"')
        filters = account_search_filters(terms)
        self.assertEqual(filters[1]["display_value"], "日本 JP")
        self.assertEqual(filters[1]["query_without"], '协议 备注:"a/b 待整理"')
        self.assertEqual([(term.field, term.value) for term in parse_account_search(filters[1]["query_without"])], [
            ("method", "protocol"), ("note", "a/b 待整理"),
        ])

    def test_quotes_and_backslashes_can_be_escaped_inside_quotes(self):
        terms = parse_account_search(r'备注:"a\"b\\c/d"')
        self.assertEqual(terms[0].value, 'a"b\\c/d')

    def test_invalid_fields_values_and_incomplete_input_have_readable_errors(self):
        for query, message in (
            ("密码:xxx", "搜索字段"), ("地区:JJ", "两位国家代码"),
            ("方式:未知", "注册方式"), ("ID:abc", "ID 必须是数字"),
            ("备注:", "缺少搜索内容"), ('备注:"未闭合', "双引号未闭合"),
            ('""', "搜索条件不能为空"),
        ):
            with self.subTest(query=query):
                with self.assertRaisesRegex(AccountSearchError, message):
                    parse_account_search(query)

    def test_query_size_and_condition_count_are_bounded(self):
        for query in ("a" * 1001, " ".join(["账号"] * 33)):
            with self.assertRaises(AccountSearchError):
                parse_account_search(query)

    def test_empty_search_has_no_conditions(self):
        self.assertEqual(parse_account_search("   "), [])
