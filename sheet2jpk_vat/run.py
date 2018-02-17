#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import calendar
from decimal import Decimal
import collections
import itertools
import argparse
from stdnum.pl import nip
from html import escape
import xmlwitch

from .utils import *
from . import ui_pyside as ui
from . import src_ods
from . import jpk_vat


def SelectFile(dir):
	files = sorted([i for i in os.listdir(dir) if i.endswith(src_ods.SupportedExts)])

	if not files:
		ui.MsgBoxCritical("Uwaga!", u"Wkazany katalog nie zawiera wspieranych plików z arkuszami.")
		raise ui.Cancelled()

	value = ui.SelectOneOf("Wybierz plik źródłowy", "Dostępne pliki w katalogu:", files)
	return os.path.join(dir, value)


def SelectSheet(ods):
	sheets = [i.name for i in ods.sheets]

	if not sheets:
		ui.MsgBoxCritical("Uwaga!", u"Wkazany plik nie zawiera poprawnych arkuszy.")
		raise ui.Cancelled()

	value = ui.SelectOneOf("Wybierz arkusz", "Dostępne arkusze:", sheets)
	return [i for i in ods.sheets if value == i.name][0]


def SelectPeriod(sells, buys):
	periods = collections.defaultdict(int)

	for priod, items in itertools.chain(sells.items(), buys.items()):
		periods[priod] += len(items)

	periods = sorted(k for k, v in periods.items() if v > 0)

	if not periods:
		ui.MsgBoxCritical("Uwaga!", u"W wskazanym arkuszu nie udało się odnaleźć poprawnych okresów.")
		raise ui.Cancelled()

	value = ui.SelectOneOf("Wybierz", "Wybierz uzupełniony okres:", periods)

	year, month = map(int, value.split('/'))
	weekday, ndays = calendar.monthrange(year, month)

	begin = datetime.date(year, month, 1)
	end = datetime.date(year, month, ndays)

	return value, begin, end


def ValidateTable(begin, end, items):

	content = jpk_vat.Validate(begin, end, items)

	if content:
		"""Pozycja 1.<br/><b class="error">Coś poszło źle</b>:</br/>"""
		dlg = ui.ReportDialog("".join(content))
		dlg.run()
		raise ui.Cancelled()


def ConfirmData(begin, end, sells, buys):

	content = []

	content.append('<b>Sprzedaż:</b><br/>')
	content.append('<table class="invoices" width="100%">')
	for i in sells:
		errors = []
		d = ExtractDate(i['Data Sprzedaży'])

		content.append('<tr>')

		content.append('<td>{}</td>'.format(escape(i['LP'])))
		content.append('<td>{}</td>'.format(escape(str(d))))
		content.append('<td>{}<br/><small>{}</small><br/><small>{}</small></td>'.format(escape(i['Nazwa Kontrahenta'] or ''), escape(i['Adres Kontrahenta'] or ''), escape(nip.format(i['NIP']))))
		content.append('<td class="currency">{:.02f} zł</td>'.format(i['Netto']))
		content.append('<td class="currency">{:.02f} zł</td>'.format(i['Kwota VAT']))

		content.append('</tr>')

	content.append('</table><br/>')

	content.append('<b>Zakupy:</b><br/>')
	content.append('<table class="invoices" width="100%">')
	for i in buys:
		errors = []
		w = ExtractDate(i['Data Wystawienia'])
		d = ExtractDate(i['Data Sprzedaży'])

		content.append('<tr>')

		content.append('<td>{}</td>'.format(escape(i['LP'])))
		content.append('<td>{}</td>'.format(escape(str(d)), escape(str(d))))
		content.append('<td>{}<br/><small>{}</small><br/><small>{}</small></td>'.format(escape(i['Nazwa Kontrahenta'] or ''), escape(i['Adres Kontrahenta'] or ''), escape(nip.format(i['NIP']))))
		content.append('<td class="currency">{:.02f} zł</td>'.format(i['Netto']))
		content.append('<td class="currency">{:.02f} zł</td>'.format(i['Kwota VAT']))

		content.append('</tr>')

	content.append('</table>')

	dlg = ui.ReportDialog("".join(content), allow_cancel=True, msg="Potwierdz poprawność odczytanych danych")
	return dlg.run() is True


def Main(argv=None):
	try:
		cmdline = argparse.ArgumentParser()
		cmdline.add_argument("--path", default="", help="Katalog z plikami ods")
		cmdline.add_argument("--nip", default="", help="NIP firmy składającej raport JPK_VAT")
		cmdline.add_argument("--name", default="", help="Pełna nazwa firmy składającej raport JPK_VAT")
		cmdline.add_argument("--email", default="", help="Adres email osoby składającej raport")
		args = cmdline.parse_args(argv)

		if not args.nip:
			raise ValueError("Podaj NIP w argumentach programu")

		if not nip.is_valid(args.nip):
			raise ValueError("Podaj poprawny NIP w argumentach programu")

		if not args.name:
			raise ValueError("Podaj pełną nazwę firmy w argumentach programu")

		filepath = SelectFile(args.path or os.getcwd())

		# TODO: Trzeba sprawdzić magic filepath i wybrać odpowiedni driver (np. src_ods) do otworzenia pliku

		src = src_ods.OpenFile(filepath)

		sheet = SelectSheet(src)
		sells, buys = src_ods.ReadData(sheet)
		period, begin, end = SelectPeriod(sells, buys)

		sells = sells.get(period) or []
		buys = buys.get(period) or []

		ValidateTable(begin, end, sells)
		ValidateTable(begin, end, buys)

		if ConfirmData(begin, end, sells, buys):
			filename = "{}_{}-{}.xml".format(os.path.splitext(filepath)[0], begin.isoformat(), end.isoformat())

			if os.path.exists(filename):
				if not ui.MsgBoxYesNo("Uwaga!", "Plik {} już istnieje.\nCzy go nadpisać nowymi danymi?".format(filename)):
					raise ui.Cancelled()

			with open(filename, "w") as xml:
				# TODO: dodać opcję wyboru złożenia dokumentu lub korekty - version
				jpk_vat.Write(xml, args.nip, args.name, args.email, begin, end, sells, buys, version=0)

		ui.MsgBoxInfo("Sukces!", "Utworzyony plik to:\n{}".format(os.path.abspath(filename)))
		return 0

	except ValueError as ex:
		print("Program napotkał błąd: {}".format(ex))
		ui.MsgBoxCritical("Program napotkał problem", str(ex))
		return 2

	except (KeyboardInterrupt, ui.Cancelled):
		return 1


if __name__ == '__main__':
	Main()