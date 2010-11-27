#	vim:fileencoding=utf-8
# Copyright 2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import portage as port
import os
from portage.output import colorize

__all__ = ['keywords_content']

from display_pretty import colorize_string
from display_pretty import align_string

class keywords_content:
	class RedundancyChecker:
		def __listRedundant(self, keywords, ignoreslots, slots):
			"""List all redundant packages."""
			if ignoreslots:
				return self.__listRedundantAll(keywords)
			else:
				return self.__listRedundantSlots(keywords, slots)

		def __listRedundantSlots(self, keywords, slots):
			"""Search for redundant packages walking per keywords for specified slot."""
			result = [self.__compareSelected([k for k, s in zip(keywords, slots)
				if s == slot])
					for slot in self.__uniq(slots)]
			# this is required because the list itself is not just one level depth
			return list(''.join(result))

		def __uniq(self, seq):
			"""Remove all duplicate elements from list."""
			seen = {}
			result = []
			for item in seq:
				if item in seen:
					continue
				seen[item] = 1
				result.append(item)
			return result

		def __cleanKeyword(self, keyword):
			"""Remove masked arches and hardmasks from keywords since we don't care about that."""
			return ["%s" % x for x in keyword.split()
				if x != '-*' and not x.startswith('-')]

		def __listRedundantAll(self, keywords):
			"""Search for redundant packages using all versions ignoring its slotting."""
			return list(self.__compareSelected(list(keywords)))

		def __compareSelected(self, kws):
			"""
			Rotate over list of keywords and compare each element with others.
			Selectively remove each already compared list from the remaining keywords.
			"""
			result = []
			kws.reverse()
			for i in range(len(kws)):
				kw = kws.pop()
				if self.__compareKeywordWithRest(kw, kws):
					result.append('#')
				else:
					result.append('o')
			if len(result) == 0:
				result.append('o')
			return ''.join(result)

		def __compareKeywordWithRest(self, keyword, keywords):
			"""Compare keywords with list of keywords."""
			kw = self.__cleanKeyword(keyword)
			for kwi in keywords:
				kwi = self.__cleanKeyword(kwi)
				if kwi:
					kw = self.__checkShadow(kw, kwi)
				if not kw:
					return True
			return False

		def __checkShadow(self, old, new):
			"""Check if package version is overshadowed by other package version."""
			tmp = set(new)
			tmp.update("~%s" % x for x in new
				if not x.startswith("~"))
			return list(set(old).difference(tmp))

		def __init__(self, keywords, slots, ignore_slots = False):
			"""Query all relevant data for redundancy package checking"""
			self.redundant = self.__listRedundant(keywords, ignore_slots, slots)

	class VersionChecker:
		def __getVersions(self, packages):
			"""Obtain properly aligned version strings without colors."""
			return map(lambda x: self.__separateVersion(x), packages)

		def __separateVersion(self, cpv):
			"""Get version string for specfied cpv"""
			#pv = port.versions.cpv_getversion(cpv)
			return self.__prependVersionInfo(cpv, self.cpv_getversion(cpv))

		# remove me when portage 2.1.9 is stable
		def cpv_getversion(self, mycpv):
			"""Returns the v (including revision) from an cpv."""
			cp = port.versions.cpv_getkey(mycpv)
			if cp is None:
				return None
			return mycpv[len(cp+"-"):]

		def __prependVersionInfo(self, cpv, pv):
			"""Prefix version with string based on whether version is installed or masked."""
			mask = self.__getMaskStatus(cpv)
			install = self.__getInstallStatus(cpv)

			if mask and install:
				pv = '[M][I]%s' % pv
			elif mask:
				pv = '[M]%s' % pv
			elif install:
				pv = '[I]%s' % pv
			return pv

		def __getMaskStatus(self, cpv):
			"""
			Figure out if package is pmasked.
			This also uses user settings in /etc/ so local changes are important.
			"""
			try:
				if port.getmaskingstatus(cpv) == ['package.mask']:
					return True
			except:
				# occurs when package is not known by portdb
				# so we consider it unmasked
				pass
			return False

		def __getInstallStatus(self, cpv):
			"""Check if package version we test is installed."""
			vartree = port.db[port.settings['ROOT']]['vartree'].dbapi
			return vartree.cpv_exists(cpv)

		def __init__(self, packages):
			"""Query all relevant data for version data formatting"""
			self.versions = self.__getVersions(packages)

	def __cpv_sort_ascending(self, cpv_list):
		"""
		Use this to sort self.cp_list() results in ascending
		order. It sorts in place and returns None.
		"""
		if len(cpv_list) > 1:
			# If the cpv includes explicit -r0, it has to be preserved
			# for consistency in findname and aux_get calls, so use a
			# dict to map strings back to their original values.
			ver_map = {}
			for cpv in cpv_list:
				cpv = cpv.split('%')[0]
				ver_map[cpv] = '-'.join(port.versions.catpkgsplit(cpv)[2:])
			def cmp_cpv(cpv1, cpv2):
				cpv1 = cpv1.split('%')[0]
				cpv2 = cpv2.split('%')[0]
				return port.versions.vercmp(ver_map[cpv1], ver_map[cpv2])
			cpv_list.sort(key=port.util.cmp_sort_key(cmp_cpv))

	def __xmatch(self, pdb, package):
		"""xmatch function that searches for all packages over all repos"""
		try:
			mycp = port.dep_expand(package, mydb=pdb, settings=pdb.settings).cp
		except port.exception.AmbiguousPackageName as Arg:
			msg_err = 'Ambiguous package name "%s".\n' % package
			found = 'Possibilities: %s' % Arg
			raise SystemExit('%s%s' % (msg_err, found))
		except port.exception.InvalidAtom:
			msg_err = 'No such package "%s"' % package
			raise SystemExit(msg_err)

		mysplit = mycp.split('/')
		d={}
		for oroot in pdb.porttrees:
			try:
				file_list = os.listdir(os.path.join(oroot, mycp))
			except OSError:
				continue
			for x in file_list:
				pf = x[:-7] if x[-7:] == '.ebuild' else []
				if pf:
					ps = port.pkgsplit(pf)
					if not ps or ps[0] != mysplit[1]:
						# we got garbage or ebuild with wrong name in the dir
						continue
					ver_match = port.versions.ver_regexp.match("-".join(ps[1:]))
					if ver_match is None or not ver_match.groups():
						# version is not allowed by portage or unset
						continue
					d[mysplit[0]+'/'+pf+'%'+oroot] = None

		mylist = list(d)
		self.__cpv_sort_ascending(mylist)
		return mylist

	def __checkExist(self, pdb, package):
		"""Check if specified package even exists."""
		matches = self.__xmatch(pdb, package)
		if len(matches) <= 0:
			msg_err = 'No such package "%s"' % package
			raise SystemExit(msg_err)
		content = [x.split('%') for x in matches]
		return list(zip(*content))

	def __getMetadata(self, pdb, packages, repos):
		"""Obtain all required metadata from portage auxdb"""
		try:
			metadata = [pdb.aux_get(pkg, ['KEYWORDS', 'SLOT'], tree)
				for pkg, tree in zip(packages, repos)]
		except KeyError:
			# portage prints out more verbose error for us if we were lucky
			raise SystemExit('Failed to obtain metadata')
		return list(zip(*metadata))

	def __formatKeywords(self, keywords, keywords_list, usebold = False, toplist = 'archlist'):
		"""Loop over all keywords and replace them with nice visual identifier"""
		# the % is fancy separator, we use it to split keywords for rotation
		# so we wont loose the empty spaces
		return ['% %'.join([self.__prepareKeywordChar(arch, i, version.split(), usebold, toplist)
			for i, arch in enumerate(keywords_list)])
				for version in keywords]

	def __prepareKeywordChar(self, arch, field, keywords, usebold = False, toplist = 'archlist'):
		"""
		Convert specified keywords for package into their visual replacements.
		# possibilities:
		# ~arch -> orange ~
		# -arch -> red -
		# arch -> green +
		# -* -> red *
		"""
		keys = [ '~%s' % arch, '-%s' % arch, '%s' % arch, '-*' ]
		values = [
			colorize('darkyellow', '~'),
			colorize('darkred', '-'),
			colorize('darkgreen', '+'),
			colorize('darkred', '*')
		]
		# check what keyword we have
		# here we cant just append space because it would get stripped later
		char = colorize('darkgray','o')
		for k, v in zip(keys, values):
			if k in keywords:
				char = v
				break
		if toplist == 'archlist' and usebold and (field)%2 == 0 and char != ' ':
			char = colorize('bold', char)
		return char

	def __formatVersions(self, versions, align, length):
		"""Append colors and align keywords properly"""
		# % are used as separators for further split so we wont loose spaces and coloring
		tmp = []
		for pv in versions:
			pv = align_string(pv, align, length)
			pv = '%'.join(list(pv))
			if pv.find('[%M%][%I%]') != -1:
				tmp.append(colorize_string('darkyellow', pv))
			elif pv.find('[%M%]') != -1:
				tmp.append(colorize_string('darkred', pv))
			elif pv.find('[%I%]') != -1:
				tmp.append(colorize_string('bold', pv))
			else:
				tmp.append(pv)
		return tmp

	def __formatAdditional(self, additional, color, length):
		"""Align additional items properly"""
		# % are used as separators for further split so we wont loose spaces and coloring
		tmp = []
		for x in additional:
			tmpc = color
			x = align_string(x, 'left', length)
			x = '%'.join(list(x))
			if x == 'o':
				# the value is unset so the color is gray
				tmpc = 'darkgray'
			x = colorize_string(tmpc, x)
			tmp.append(x)
		return tmp

	def __prepareContentResult(self, versions, keywords, redundant, slots, slot_length, repos, linesep):
		"""Parse version fields into one list with proper separators"""
		content = []
		oldslot = ''
		fieldsep = '% %|% %'
		normsep = '% %'
		for v, k, r, s, t in zip(versions, keywords, redundant, slots, repos):
			if oldslot != s:
				oldslot = s
				content.append(linesep)
			else:
				s = '%'.join(list(''.rjust(slot_length)))
			content.append('%s%s%s%s%s%s%s%s%s' % (v, fieldsep, k, fieldsep, r, normsep, s, fieldsep, t))
		return content

	def __init__(self, package, keywords_list, porttree, ignoreslots = False, content_align = 'bottom', usebold = False, toplist = 'archlist'):
		"""Query all relevant data from portage databases."""
		packages, self.repositories = self.__checkExist(porttree, package)
		self.keywords, self.slots = self.__getMetadata(porttree, packages, self.repositories)
		# convert repositories from path to name
		self.repositories = [porttree.getRepositoryName(x) for x in self.repositories]
		self.slot_length = max([len(x) for x in self.slots])
		repositories_length = max([len(x) for x in self.repositories])
		self.keyword_length = len(keywords_list)
		self.versions = self.VersionChecker(packages).versions
		self.version_length = max([len(x) for x in self.versions])
		self.version_count = len(self.versions)
		self.redundant = self.RedundancyChecker(self.keywords, self.slots, ignoreslots).redundant
		redundant_length = max([len(x) for x in self.redundant])

		ver = self.__formatVersions(self.versions, content_align, self.version_length)
		kws = self.__formatKeywords(self.keywords, keywords_list, usebold, toplist)
		red = self.__formatAdditional(self.redundant, 'purple', redundant_length)
		slt = self.__formatAdditional(self.slots, 'bold', self.slot_length)
		rep = self.__formatAdditional(self.repositories, 'yellow', repositories_length)
		# those + nubers are spaces in printout. keywords are multiplied also because of that
		linesep = '%s+%s+%s+%s' % (''.ljust(self.version_length+1, '-'),
			''.ljust(self.keyword_length*2+1, '-'),
			''.ljust(redundant_length+self.slot_length+3, '-'),
			''.ljust(repositories_length+1, '-')
		)

		self.content = self.__prepareContentResult(ver, kws, red, slt, self.slot_length, rep, linesep)
		self.content_length = len(linesep)
		self.cp = port.cpv_getkey(packages[0])
