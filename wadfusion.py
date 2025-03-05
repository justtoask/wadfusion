##-----------------------------------------------------------------------------
##
## Copyright 2024-2025 Owlet VII
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see http://www.gnu.org/licenses/
##
##-----------------------------------------------------------------------------
##

##
## This code is derived from WadSmoosh 1.41, which is covered by the following permissions:
##
##------------------------------------------------------------------------------------------
##
## The MIT License (MIT)
## 
## Copyright (c) 2016-2023 JP LeBreton
## 
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
## 
## The above copyright notice and this permission notice shall be included in
## all copies or substantial portions of the Software.
## 
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
## IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
## AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
## THE SOFTWARE.
##
##------------------------------------------------------------------------------------------
##

import platform, os, sys, time, fnmatch
from shutil import copyfile, rmtree
from zipfile import ZipFile, ZIP_DEFLATED
from os import path

import omg

VERSION = '1.4.1'

# if False, do a dry run with no actual file writing
should_extract = True

SRC_WAD_DIR = 'source_wads/'
DATA_DIR = 'data/'
DEST_DIR = 'temp/'
DEST_FILENAME = 'doom_fusion.ipk3'
LOG_FILENAME = 'wadfusion.log'
RES_DIR = 'res/'
DEST_DIR_MUS = DEST_DIR + 'music/'
DEST_DIR_GRAPHICS = DEST_DIR + 'graphics/'
# abspath is used for the sake of the Windows executable, which bundles wadfusion_data.py
DATA_TABLES_FILE = path.abspath(path.join(path.dirname(__file__), 'wadfusion_data.py'))

# forward-declare all the stuff in DATA_TABLES_FILE for clarity
RES_FILES = []
WADS = []
REPORT_WADS = []
COMMON_LUMPS = []
DOOM1_LUMPS = []
DOOM2_LUMPS = []
WAD_LUMP_LISTS = {}
WAD_MAP_PREFIXES = {}
MAP_NAME_GRAPHICS_DIRS = []
MASTER_LEVELS_ORDER = []
MASTER_LEVELS_REJECTS_ORDER = []
MASTER_LEVELS_PATCHES = {}
MASTER_LEVELS_TITAN_PATCHES = {}
MASTER_LEVELS_UDTWID_PATCHES = {}
SIGIL_ALT_FILENAMES = []
SIGIL2_ALT_FILENAMES = []
SIGIL2_MP3_ALT_FILENAMES = []
REGISTERED_DOOM_ONLY_LUMP = ''
ULTIMATE_DOOM_ONLY_LUMP = ''
NERVE_UNITY_KEX_ONLY_LUMP = ''
EXTRAS_KEX_ONLY_LUMP = ''

logfile = None

exec(open(DATA_TABLES_FILE).read())

MASTER_LEVELS_MAP_PREFIX = WAD_MAP_PREFIXES.get('masterlevels', '')

should_extract_master_levels_rejects = False

# track # of maps extracted
num_maps = 0
num_errors = 0


def logg(line, error=False):
    global logfile, num_errors
    if not logfile:
        logfile = open(LOG_FILENAME, 'w', encoding='utf-8')
    print(line)
    logfile.write(line + '\n')
    if error:
        num_errors += 1

def logs(line, error=False):
    global logfile, num_errors
    if not logfile:
        logfile = open(LOG_FILENAME, 'w', encoding='utf-8')
    logfile.write(line + '\n')
    if error:
        num_errors += 1

def get_wad_filename(wad_name):
    # return filename of first case-insensitive match
    wad_name += '.wad'
    for filename in os.listdir(SRC_WAD_DIR):
        if wad_name.lower() == filename.lower():
            return SRC_WAD_DIR + filename
    return None

def extract_master_levels():
    # check if present first
    for i, wad_name in enumerate(MASTER_LEVELS_ORDER):
        in_wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        if not wad_filename:
            logg("  ERROR: Skipping Master Levels as %s is not present" % wad_name, error=True)
            return
    logs('Processing Master Levels...')
    for i, wad_name in enumerate(MASTER_LEVELS_ORDER):
        in_wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        in_wad.from_file(wad_filename)
        out_wad_filename = DEST_DIR + 'maps/' + MASTER_LEVELS_MAP_PREFIX + 'MAP'
        # extra zero for <10 map numbers, eg map01
        out_wad_filename += str(i + 1).rjust(2, '0') + '.wad'
        logs('  Extracting %s to %s' % (wad_filename, out_wad_filename))
        # grab first map we find in each wad
        map_name = in_wad.maps.find('*')[0]
        extract_map(in_wad, map_name, out_wad_filename)
    # save teeth map32 to map21
    wad_filename = get_wad_filename('teeth')
    out_wad_filename = DEST_DIR + 'maps/' + MASTER_LEVELS_MAP_PREFIX + 'MAP21' + '.wad'
    logs('  Extracting %s map32 to %s' % (wad_filename, out_wad_filename))
    in_wad = omg.WAD()
    in_wad.from_file(wad_filename)
    extract_map(in_wad, in_wad.maps.find('*')[1], out_wad_filename)
    # extract sky lumps
    for wad_name, patch_replace in MASTER_LEVELS_PATCHES.items():
        wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        wad.from_file(wad_filename)
        # manor stores sky in patches namespace, combine and virgil don't
        if patch_replace[0] in wad.data:
            lump = wad.data[patch_replace[0]]
        else:
            lump = wad.patches[patch_replace[0]]
        out_filename = DEST_DIR + 'patches/' + patch_replace[1] + '.lmp'
        logs('  Extracting %s lump from %s as %s' % (patch_replace[0],
                                                   wad_filename,
                                                   patch_replace[1]))
        lump.to_file(out_filename)

def copy_master_levels_doom1_music():
    logs('Duplicating D_RUNNIN.mus to use in the Master Levels in place of Doom1 music...')
    copyfile(DEST_DIR_MUS + 'D_RUNNIN.mus', DEST_DIR_MUS + 'D_E2M2.mus')
    copyfile(DEST_DIR_MUS + 'D_RUNNIN.mus', DEST_DIR_MUS + 'D_E1M6.mus')
    copyfile(DEST_DIR_MUS + 'D_RUNNIN.mus', DEST_DIR_MUS + 'D_E3M3.mus')
    copyfile(DEST_DIR_MUS + 'D_RUNNIN.mus', DEST_DIR_MUS + 'D_E1M7.mus')

def extract_master_levels_rejects():
    global num_maps, should_extract_master_levels_rejects
    # check if present first
    for i, wad_name in enumerate(MASTER_LEVELS_ORDER):
        in_wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        if not (wad_filename or get_wad_filename('masterlevels')):
            logg("  ERROR: Skipping Master Levels Rejects as the Master Levels are not present", error=True)
            return
    for i, wad_name in enumerate(MASTER_LEVELS_REJECTS_ORDER):
        in_wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        if not wad_filename:
            logg("  ERROR: Skipping Master Levels Rejects as %s is not present" % wad_name, error=True)
            return
    if not get_wad_filename('udtwid'):
        logg("  ERROR: Skipping Master Levels Rejects as udtwid.wad is not present", error=True)
        return
    if not get_wad_filename('caball'):
        logg("  ERROR: Skipping Master Levels Rejects as caball.wad is not present", error=True)
        return
    d1_wad = omg.WAD()
    if get_wad_filename('doom'):
        d1_wad.from_file(get_wad_filename('doom'))
    if not d1_wad.graphics.get(ULTIMATE_DOOM_ONLY_LUMP, None):
        logg("  ERROR: Skipping Master Levels Rejects as The Ultimate DOOM is not present", error=True)
        return
    should_extract_master_levels_rejects = True
    logs('Processing Master Levels Rejects...')
    for i, wad_name in enumerate(MASTER_LEVELS_REJECTS_ORDER):
        in_wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        in_wad.from_file(wad_filename)
        out_wad_filename = DEST_DIR + 'maps/' + MASTER_LEVELS_MAP_PREFIX + 'MAP'
        out_wad_filename += str(i + 22) + '.wad'
        logs('  Extracting %s to %s' % (wad_filename, out_wad_filename))
        # grab first map we find in each wad
        map_name = in_wad.maps.find('*')[0]
        extract_map(in_wad, map_name, out_wad_filename)
    # copy E4M7 to use as John Anderson's 8th Canto
    out_wad_filename = DEST_DIR + 'maps/' + 'ML_MAP35.wad'
    logs('  Copying %s map E4M8 to %s' % (get_wad_filename('doom'), out_wad_filename))
    copyfile(DEST_DIR + 'maps/' + 'E4M7.wad', out_wad_filename)
    num_maps += 1
    # copy UDTWiD E4M8 into dest dir and set its map lump name
    in_wad = omg.WAD()
    wad_filename = get_wad_filename('udtwid')
    in_wad.from_file(wad_filename)
    out_wad_filename = DEST_DIR + 'maps/' + 'ML_MAP36.wad'
    logs('  Extracting %s map E4M8 to %s' % (wad_filename, out_wad_filename))
    map_name = in_wad.maps.find('E4M8')[0]
    extract_map(in_wad, map_name, out_wad_filename)
    # copy cabal maps
    i = 0
    in_wad = omg.WAD()
    wad_filename = get_wad_filename('caball')
    in_wad.from_file(wad_filename)
    for map_name in in_wad.maps.find('*'):
        out_wad_filename = DEST_DIR + 'maps/' + MASTER_LEVELS_MAP_PREFIX + 'MAP'
        out_wad_filename += str(i + 37) + '.wad'
        logs('  Extracting %s map %s to %s' % (wad_filename, map_name, out_wad_filename))
        extract_map(in_wad, map_name, out_wad_filename)
        i += 1
    # extract Titan lumps
    for wad_name, patch_extract in MASTER_LEVELS_TITAN_PATCHES.items():
        wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        wad.from_file(wad_filename)
        for i in patch_extract:
            lump = wad.patches[i]
            out_filename = DEST_DIR + 'patches/' + i + '.lmp'
            logs('  Extracting %s lump from %s' % (i, wad_filename))
            lump.to_file(out_filename)
    # extract UDTWiD lumps
    wad = omg.WAD()
    wad_filename = get_wad_filename('udtwid')
    wad.from_file(wad_filename)
    lump = wad.patches['DRSLEEP']
    out_filename = DEST_DIR + 'patches/DRSLEEP.lmp'
    logs('  Extracting DRSLEEP lump from %s' % wad_filename)
    lump.to_file(out_filename)
    for wad_name, patch_replace in MASTER_LEVELS_UDTWID_PATCHES.items():
        wad = omg.WAD()
        wad_filename = get_wad_filename(wad_name)
        wad.from_file(wad_filename)
        lump = wad.patches[patch_replace[0]]
        out_filename = DEST_DIR + 'patches/' + patch_replace[1] + '.lmp'
        logs('  Extracting %s lump from %s as %s' % (patch_replace[0],
                                                   wad_filename,
                                                   patch_replace[1]))
        lump.to_file(out_filename)

def enable_master_levels_rejects():
    logs('Enabling Master Levels Rejects...')
    # copy rejects-specific mapinfo
    copyfile(RES_DIR + 'mapinfo.rejects.txt', DEST_DIR + 'mapinfo.txt')

def rename_ogg():
    # remove .lmp file extension from Andrew Hulshult's IDKFA .ogg music if it's present
    logs('Renaming OGG music files if present...')
    # the music gets extracted to the graphics folder first
    for filename in os.listdir(DEST_DIR_GRAPHICS):
        if fnmatch.fnmatch(filename, '*.ogg.lmp'):
            old_name = os.path.join(DEST_DIR_GRAPHICS, filename)
            new_name = old_name.replace('.ogg.lmp', '.ogg')
            # set the destination for the music files to the music folder
            new_name = new_name.replace('graphics', 'music')
            logs('  Moving %s lump to %s' % (old_name, new_name))
            os.rename(old_name, new_name)

def rename_mp3():
    # remove .mus file extension from Sigil's .mp3 music if it's present
    logs('Renaming MP3 music files if present...')
    for filename in os.listdir(DEST_DIR_MUS):
        if fnmatch.fnmatch(filename, '*.mp3.mus'):
            old_name = os.path.join(DEST_DIR_MUS, filename)
            new_name = old_name.replace('.mp3.mus', '.mp3')
            logs('  Moving %s lump to %s' % (old_name, new_name))
            os.rename(old_name, new_name)

def add_xbox_levels():
    global num_maps
    logs('Adding Xbox bonus levels...')
    if get_wad_filename('doom') and get_wad_filename('sewers'):
        logs('  Adding SEWERS.WAD as E1M10')
        copyfile(get_wad_filename('sewers'), DEST_DIR + 'maps/E1M10.wad')
        num_maps += 1
    if get_wad_filename('doom2') and get_wad_filename('betray'):
        logs('  Adding BETRAY.WAD as MAP33')
        copyfile(get_wad_filename('betray'), DEST_DIR + 'maps/MAP33.wad')
        num_maps += 1

def add_blackroom_levels():
    global num_maps
    logs('Adding Blackroom warm-up levels...')
    if get_wad_filename('doom') and get_wad_filename('e1m4b'):
        logs('  Adding E1M4B.WAD as E1M4B')
        copyfile(get_wad_filename('e1m4b'), DEST_DIR + 'maps/E1M4B.wad')
        num_maps += 1    
    if get_wad_filename('doom') and get_wad_filename('e1m8b'):
        logs('  Adding E1M8B.WAD as E1M8B')
        copyfile(get_wad_filename('e1m8b'), DEST_DIR + 'maps/E1M8B.wad')
        num_maps += 1

def extract_map(in_wad, map_name, out_filename):
    global num_maps
    out_wad = omg.WAD()
    out_wad.maps[map_name] = in_wad.maps[map_name]
    out_wad.to_file(out_filename)
    num_maps += 1

def extract_iwad_maps(wad_name, map_prefix):
    in_wad = omg.WAD()
    wad_filename = get_wad_filename(wad_name)
    in_wad.from_file(wad_filename)
    for map_name in in_wad.maps.find('*'):
        logs('  Extracting map %s...' % map_name)
        out_wad_filename = DEST_DIR + 'maps/' + map_prefix + map_name + '.wad'
        extract_map(in_wad, map_name, out_wad_filename)
        #logs('  Saved map %s' % out_wad_filename)

def extract_lumps(wad_name):
    if not wad_name in WAD_LUMP_LISTS:
        return
    wad = omg.WAD()
    wad_filename = get_wad_filename(wad_name)
    wad.from_file(wad_filename)
    for lump_list in WAD_LUMP_LISTS[wad_name]:
        # derive subdir from name of lump list
        try:
            lump_type = lump_list[:lump_list.index('_')]
        except ValueError:
            logg("  ERROR: Couldn't identify type of lump list %s" % lump_list, error=True)
            continue
        # sigil sky lump isn't in patch namespace
        if lump_list == 'patches_sigil':
            lump_type = 'data'
        # the IDKFA soundtrack isn't in music namespace
        if lump_list == 'music_extras':
            lump_type = 'data'
        lump_table = getattr(wad, lump_type, None)
        if not lump_table:
            logg('  ERROR: Lump type %s not found' % lump_type, error=True)
            continue
        logs('  extracting %s...' % lump_list)
        # sigil sky is in data namespace but we want it in patches dir
        if wad_name == 'sigil' and lump_list == 'patches_sigil':
            lump_subdir = DEST_DIR + 'patches/'
        # sigil 1&2 screens aren't in graphics namespace but belong in that dir
        elif wad_name == 'sigil' and lump_type == 'data':
            lump_subdir = DEST_DIR + 'graphics/'
        elif wad_name == 'sigil2' and lump_type == 'data':
            lump_subdir = DEST_DIR + 'graphics/'
        # legacy of rust statusbar icons and map title patches aren't in graphics namespace but belong in that dir
        elif wad_name == 'id1' and lump_type == 'data':
            lump_subdir = DEST_DIR + 'graphics/'
        # extras.wad statusbar icons aren't in graphics namespace but belong in that dir
        elif wad_name == 'extras' and lump_type == 'data':
            lump_subdir = DEST_DIR + 'graphics/'
        # write PLAYPAL, TEXTURE1 etc to pk3 root
        elif lump_type in ['data', 'txdefs']:
            lump_subdir = DEST_DIR
        else:
            lump_subdir = DEST_DIR + lump_type + '/'
        # process each item in lump list
        for line in open(DATA_DIR + lump_list).readlines():
            line = line.strip()
            # ignore comments
            if line.startswith('//'):
                continue
            # no colon: extracted lump uses name from list
            if line.find(':') == -1:
                out_filename = line
                lump_name = line
            # colon: use filename to right of colon
            else:
                # split then strip
                lump_name, out_filename = line.split(':')
                lump_name = lump_name.strip()
                out_filename = out_filename.strip()
            if not lump_name in lump_table:
                logg("  ERROR: Couldn't find lump with name %s" % lump_name, error=True)
                continue
            lump = lump_table[lump_name]
            out_filename += '.lmp' if lump_type != 'music' else '.mus'
            logs('    Extracting %s' % lump_subdir + out_filename)
            lump.to_file(lump_subdir + out_filename)

def copy_resources():
    d1_wad = omg.WAD()
    if get_wad_filename('doom'):
        d1_wad.from_file(get_wad_filename('doom'))
    for src_file in RES_FILES:
        # don't copy texture lumps for files that aren't present
        if src_file == 'textures.doom1' and not (get_wad_filename('doom') and d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None)):
            # DO copy if id1 or iddm1 exists and doom1 doesn't
            if not ((get_wad_filename('doom2') and get_wad_filename('id1') and get_wad_filename('id1-res') and get_wad_filename('id24res')) or (get_wad_filename('doom2') and get_wad_filename('iddm1'))):
                continue
        elif src_file == 'textures.doom2' and not get_wad_filename('doom2'):
            # DO copy if final doom exists and doom2 doesn't
            if not get_wad_filename('tnt'):
                if not get_wad_filename('plutonia'):
                    continue
        elif src_file == 'textures.tnt' and not get_wad_filename('tnt'):
            continue
        elif src_file == 'textures.plut' and not get_wad_filename('plutonia'):
            if not get_wad_filename('tnt'):
                continue
        elif src_file == 'textures.id1' and not (get_wad_filename('doom2') and get_wad_filename('id1') and get_wad_filename('id1-res') and get_wad_filename('id24res')):
            if not (get_wad_filename('doom2') and get_wad_filename('iddm1')):
                continue
        elif src_file == 'textures.masterlevels' and not (get_wad_filename('doom2') and (get_wad_filename('attack') or get_wad_filename('masterlevels'))):
            continue
        elif src_file == 'textures.masterlevelsbonus' and not (get_wad_filename('doom') and get_wad_filename('doom2') and (get_wad_filename('attack') or get_wad_filename('masterlevels')) and get_wad_filename('mines') and d1_wad.graphics.get(ULTIMATE_DOOM_ONLY_LUMP, None)):
            continue
        logs('Copying %s' % src_file)
        copyfile(RES_DIR + src_file, DEST_DIR + src_file)

def copy_id1_doom1_skies():
    logs('Duplicating doom1 sky patches to suppress errors with id1...')
    copyfile(DEST_DIR + 'patches/SKYE1.lmp', DEST_DIR + 'patches/SKY1.lmp')
    copyfile(DEST_DIR + 'patches/SKYE2.lmp', DEST_DIR + 'patches/SKY2.lmp')
    copyfile(DEST_DIR + 'patches/SKYE3.lmp', DEST_DIR + 'patches/SKY3.lmp')
    copyfile(DEST_DIR + 'patches/SKYE4.lmp', DEST_DIR + 'patches/SKY4.lmp')

def get_report_found():
    found = []
    for wadname in REPORT_WADS:
        if get_wad_filename(wadname):
            found.append(wadname)
    # look for sigil by other names
    if 'doom' in found and not 'sigil' in found:
        for alt_name in SIGIL_ALT_FILENAMES:
            sigil_alt = get_wad_filename(alt_name)
            # rather than handle variable filename for it, just create
            # a copy in source_wads/ with the expected name
            if sigil_alt:
                os.rename(sigil_alt, SRC_WAD_DIR + 'SIGIL.WAD')
                found.insert(1, 'sigil')
                break
    # same with sigil2
    # (TODO maybe some way to generalize this for future releases?)
    if 'doom' in found and not 'sigil2' in found:
        for alt_name in SIGIL2_ALT_FILENAMES:
            sigil2_alt = get_wad_filename(alt_name)
            if sigil2_alt:
                os.rename(sigil2_alt, SRC_WAD_DIR + 'SIGIL2.WAD')
                found.insert(2, 'sigil2')
                break
    # ... and sigil2 mp3 soundtrack version
    if 'sigil2' in found and not 'sigil2_mp3' in found:
        for alt_name in SIGIL2_MP3_ALT_FILENAMES:
            sigil2_mp3_alt = get_wad_filename(alt_name)
            if sigil2_mp3_alt:
                os.rename(sigil2_mp3_alt, SRC_WAD_DIR + 'SIGIL2_MP3.WAD')
                found.insert(3, 'sigil2_mp3')
                break
    return found

def clear_temp():
    # clear out temp dir from previous runs
    if os.path.exists(DEST_DIR):
        rmtree(DEST_DIR)
        logs('Removed temp directory from a previous run.\n')

def get_eps(wads_found):
    d1_wad = omg.WAD()
    if get_wad_filename('doom'):
        d1_wad.from_file(get_wad_filename('doom'))
    eps = []
    for wadname in wads_found:
        if wadname == 'doom':
            if d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
                eps += ['Knee Deep in the Dead', 'The Shores of Hell', 'Inferno']
                if d1_wad.graphics.get(ULTIMATE_DOOM_ONLY_LUMP, None):
                    eps += ['Thy Flesh Consumed']
        elif wadname == 'doom2':
            eps += ['Hell on Earth']
        elif wadname == 'attack' and not 'masterlevels' in wads_found and 'doom2' in wads_found and not 'device_1' in wads_found:
            eps += ['Master Levels']
        elif wadname == 'masterlevels' and 'doom2' in wads_found and not 'device_1' in wads_found:
            eps += ['Master Levels']
        elif wadname == 'device_1' and ('attack' in wads_found or 'masterlevels' in wads_found) and 'doom2' in wads_found:
            eps += ['Tim Willits (Master Levels)', 'Christen Klie (Master Levels)', 'Tom Mustaine (Master Levels)', 'Jim Flynn\'s Titan (Master Levels)', 'John Anderson\'s INFERNO (Master Levels)', 'Sverre André Kvernmo\'s CABAL (Master Levels)']
        elif wadname == 'nerve' and 'doom2' in wads_found:
            eps += ['No Rest for the Living']
        elif wadname == 'tnt':
            eps += ['TNT: Evilution']
        elif wadname == 'plutonia':
            eps += ['The Plutonia Experiment']
        elif wadname == 'sigil' and 'doom' in wads_found:
            if d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
                eps += ['SIGIL']
        elif wadname == 'sigil2' and 'doom' in wads_found:
            if d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
                eps += ['SIGIL II']
        elif wadname == 'id1' and 'doom2' in wads_found and 'id1-res' in wads_found and 'id24res' in wads_found:
            eps += ['The Vulcan Abyss', 'Counterfeit Eden']
        elif wadname == 'iddm1' and 'doom2' in wads_found:
            eps += ['id Deathmatch Pack #1']
    return eps

def pk3_compress():
    logg('Compressing %s...' % DEST_FILENAME)
    pk3 = ZipFile(DEST_FILENAME, 'w', ZIP_DEFLATED)
    for dir_name, x, filenames in os.walk(DEST_DIR):
        for filename in filenames:
            src_name = dir_name + '/' + filename
            # exclude pk3/ top dir from name within archive
            dest_name = src_name[len(DEST_DIR):]
            pk3.write(src_name, dest_name)
    pk3.close()

def main():
    # log python and os version
    logs(sys.version)
    logs(platform.system() + ' ' + os.name + ' ' + sys.platform + ' ' + platform.release())
    logs(platform.version())
    logs(platform.platform() + '\n')
    # clear out pk3 dir from previous runs
    clear_temp()
    title_line = 'WadFusion v%s' % VERSION
    logg(title_line + '\n' + '-' * len(title_line) + '\n')
    found = get_report_found()
    # bail if no wads in SRC_WAD_DIR
    if len(found) == 0:
        logg('No source WADs found!\nPlease place your WAD files into %s.' % os.path.realpath(SRC_WAD_DIR))
        logfile.close()
        input('Press Enter to exit.\n')
        return
    logs('Found in %s:\n' % SRC_WAD_DIR + ', '.join(found) + '\n')
    # bail if no iwads in SRC_WAD_DIR
    if not get_wad_filename('doom') and not get_wad_filename('doom2') and not get_wad_filename('tnt') and not get_wad_filename('plutonia'):
        logg('No source IWADs found!\nPlease place your IWAD files into %s.' % os.path.realpath(SRC_WAD_DIR))
        logfile.close()
        input('Press Enter to exit.\n')
        return
    logg('A new IPK3 will be generated with the following episodes:')
    for num_eps, ep_name in enumerate(get_eps(found)):
        logg('- %s' % ep_name)
    num_eps += 1
    # deduct iddm1 from the episode tally, since it won't show up in the menu
    if get_wad_filename('iddm1') and get_wad_filename('doom2'):
        num_eps -= 1
    i = input('\nPress Y and then Enter to proceed, anything else to cancel: ')
    if i.lower() != 'y':
        logg('Canceled.')
        logfile.close()
        return
    start_time = time.time()
    logg('\nProcessing WADs...')
    # make dirs if they don't exist
    if not os.path.exists(DEST_DIR):
        os.mkdir(DEST_DIR)
    for dirname in ['flats', 'graphics', 'music', 'maps', 'mapinfo',
                    'patches', 'sounds', 'sprites', 'zscript']:
        if not os.path.exists(DEST_DIR + dirname):
            os.mkdir(DEST_DIR + dirname)
    # if final doom present but not doom1/2, extract doom2 resources from it
    if (get_wad_filename('tnt') or get_wad_filename('plutonia')) and not get_wad_filename('doom2'):
        if get_wad_filename('tnt') and not get_wad_filename('plutonia'):
            logg('  ERROR: Extracting doom2.wad resources from tnt.wad as doom2.wad is not present', error=True)
            WAD_LUMP_LISTS['tnt'] += DOOM2_LUMPS
        else:
            logg('  ERROR: Extracting doom2.wad resources from plutonia.wad as doom2.wad is not present', error=True)
            WAD_LUMP_LISTS['plutonia'] += DOOM2_LUMPS
        # if doom 1 also isn't present (weird) extract all common resources
        if not get_wad_filename('doom'):
            if get_wad_filename('tnt') and not get_wad_filename('plutonia'):
                logg('  ERROR: Extracting common resources from tnt.wad as doom.wad or doom2.wad are not present', error=True)
                WAD_LUMP_LISTS['tnt'] += COMMON_LUMPS
            else:
                logg('  ERROR: Extracting common resources from plutonia.wad as doom.wad or doom2.wad are not present', error=True)
                WAD_LUMP_LISTS['plutonia'] += COMMON_LUMPS
    d1_wad = omg.WAD()
    if get_wad_filename('doom'):
        d1_wad.from_file(get_wad_filename('doom'))
    # if id1 present but not doom1, extract doom1 resources from it
    if get_wad_filename('id1') and not (get_wad_filename('doom') and d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None)):
        logg('  ERROR: Extracting doom.wad resources from iddm1.wad as doom.wad is not present', error=True)
        WAD_LUMP_LISTS['id1'] += ['patches_doom1']
    # if iddm1 present but not id1, extract id1 resources from it
    if get_wad_filename('iddm1') and not get_wad_filename('id1'):
        logg('  ERROR: Extracting id1.wad resources from iddm1.wad as id1.wad is not present', error=True)
        WAD_LUMP_LISTS['iddm1'] += ID1_LUMPS
    # if iddm1 present but not doom1, extract doom1 music from it
    if get_wad_filename('iddm1') and not get_wad_filename('doom'):
        logg('  ERROR: Extracting doom.wad resources from iddm1.wad as doom.wad is not present', error=True)
        WAD_LUMP_LISTS['iddm1'] += ['music_doom1', 'patches_doom1']
    # if iddm1 present but not tnt, extract tnt music from it
    if get_wad_filename('iddm1') and not get_wad_filename('tnt'):
        logg('  ERROR: Extracting tnt.wad resources from iddm1.wad as tnt.wad is not present', error=True)
        WAD_LUMP_LISTS['iddm1'] += ['music_iddm1']
    # if nerve is the unity or kex version
    if get_wad_filename('nerve'):
        nerve_wad = omg.WAD()
        nerve_wad.from_file(get_wad_filename('nerve'))
        if nerve_wad.graphics.get(NERVE_UNITY_KEX_ONLY_LUMP, None):
            WAD_LUMP_LISTS['nerve'] += ['graphics_nerveunity']
    # if extras is the kex version
    if get_wad_filename('extras') and should_extract:
        extras_wad = omg.WAD()
        extras_wad.from_file(get_wad_filename('extras'))
        if extras_wad.colormaps.get(EXTRAS_KEX_ONLY_LUMP, None):
            WAD_LUMP_LISTS['extras'] += ['graphics_extras', 'music_extras']
    # extract lumps and maps from wads
    for iwad_name in WADS:
        wad_filename = get_wad_filename(iwad_name)
        if not wad_filename:
            logs('WAD %s not found' % iwad_name)
            continue
        if iwad_name == 'masterlevels' and not get_wad_filename('doom2'):
            logg('  ERROR: Skipping masterlevels.wad as doom2.wad is not present', error=True)
            continue
        if iwad_name == 'nerve' and not get_wad_filename('doom2'):
            logg('  ERROR: Skipping nerve.wad as doom2.wad is not present', error=True)
            continue
        if iwad_name == 'sigil' and not get_wad_filename('doom'):
            logg('  ERROR: Skipping sigil.wad as doom.wad is not present', error=True)
            continue
        if iwad_name == 'sigil_shreds' and not get_wad_filename('sigil'):
            logg('  ERROR: Skipping sigil_shreds.wad as sigil.wad is not present', error=True)
            continue
        if iwad_name == 'sigil_shreds' and not get_wad_filename('doom'):
            logg('  ERROR: Skipping sigil_shreds.wad as doom.wad is not present', error=True)
            continue
        if iwad_name == 'sigil2' and not get_wad_filename('doom'):
            logg('  ERROR: Skipping sigil2.wad as doom.wad is not present', error=True)
            continue
        if iwad_name == 'sigil2_mp3' and not get_wad_filename('sigil2'):
            logg('  ERROR: Skipping sigil2_mp3.wad as sigil2.wad is not present', error=True)
            continue
        if iwad_name == 'sigil2_mp3' and not get_wad_filename('doom'):
            logg('  ERROR: Skipping sigil2_mp3.wad as doom.wad is not present', error=True)
            continue
        if iwad_name == 'id1' and not get_wad_filename('doom2'):
            logg('  ERROR: Skipping id1.wad as doom2.wad is not present', error=True)
            continue
        if iwad_name == 'id1' and not get_wad_filename('id1-res'):
            logg('  ERROR: Skipping id1.wad as id1-res.wad is not present', error=True)
            continue
        if iwad_name == 'id1' and not get_wad_filename('id24res'):
            logg('  ERROR: Skipping id1.wad as id24res.wad is not present', error=True)
            continue
        if iwad_name == 'iddm1' and not get_wad_filename('doom2'):
            logg('  ERROR: Skipping iddm1.wad as doom2.wad is not present', error=True)
            continue
        if iwad_name == 'doom' and not d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
            logg('  ERROR: Skipping doom.wad as it appears to be the shareware version', error=True)
            continue
        if iwad_name == 'sigil' and not d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
            logg('  ERROR: Skipping sigil.wad as doom.wad appears to be the shareware version', error=True)
            continue
        if iwad_name == 'sigil_shreds' and not d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
            logg('  ERROR: Skipping sigil_shreds.wad as doom.wad appears to be the shareware version', error=True)
            continue
        if iwad_name == 'sigil2' and not d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
            logg('  ERROR: Skipping sigil2.wad as doom.wad appears to be the shareware version', error=True)
            continue
        if iwad_name == 'sigil2_mp3' and not d1_wad.sprites.get(REGISTERED_DOOM_ONLY_LUMP, None):
            logg('  ERROR: Skipping sigil2_mp3.wad as doom.wad appears to be the shareware version', error=True)
            continue
        logs('Processing WAD %s...' % iwad_name)
        if should_extract:
            extract_lumps(iwad_name)
            prefix = WAD_MAP_PREFIXES.get(iwad_name, None)
            # check None, not empty string!
            if prefix is not None:
                extract_iwad_maps(iwad_name, prefix)
    if get_wad_filename('attack') and get_wad_filename('doom2') and not get_wad_filename('masterlevels'):
        if should_extract:
            extract_master_levels()
    elif get_wad_filename('attack') and not get_wad_filename('doom2'):
        logg('  ERROR: Skipping Master Levels as doom2.wad is not present', error=True)
    if (get_wad_filename('attack') or get_wad_filename('masterlevels')) and not get_wad_filename('doom') and should_extract:
        copy_master_levels_doom1_music()
    if get_wad_filename('device_1') and (get_wad_filename('attack') or get_wad_filename('masterlevels')) and get_wad_filename('doom2'):
        if should_extract:
            extract_master_levels_rejects()
    elif get_wad_filename('device_1') and not get_wad_filename('doom2'):
        logg('  ERROR: Skipping Master Levels Rejects as doom2.wad is not present', error=True)
    elif get_wad_filename('device_1') and not (get_wad_filename('attack') or get_wad_filename('masterlevels')):
        logg('  ERROR: Skipping Master Levels Rejects as the Master Levels are not present', error=True)
    # copy pre-authored lumps eg mapinfo
    if should_extract:
        copy_resources()
    # copy and enable Master levels Rejects mapinfo
    if should_extract_master_levels_rejects:
        enable_master_levels_rejects()
    # duplicate doom1 sky patches to suppress errors with id1
    if get_wad_filename('id1') and get_wad_filename('id1-res') and get_wad_filename('id24res') and get_wad_filename('doom2') and not get_wad_filename('doom') and should_extract:
        copy_id1_doom1_skies()
    # rename file extensions of Sigil mp3 music
    if should_extract:
        rename_mp3()
    # rename file extensions of Andrew Hulshult's IDKFA soundtrack ogg music
    if should_extract:
        rename_ogg()
    # only supported versions of these @ http://classicdoom.com/xboxspec.htm
    if (get_wad_filename('sewers') or get_wad_filename('betray')) and should_extract:
        add_xbox_levels()
    # add romero's blackroom warm-up levels if present
    if (get_wad_filename('e1m4b') or get_wad_filename('e1m8b')) and should_extract:
        add_blackroom_levels() 
    # copy custom GENMIDI, if user hasn't deleted it
    genmidi_filename = 'GENMIDI.lmp'
    if os.path.exists(RES_DIR + genmidi_filename):
        logs('Copying %s' % genmidi_filename)
        copyfile(RES_DIR + genmidi_filename, DEST_DIR + genmidi_filename)
    # create pk3
    pk3_compress()
    elapsed_time = time.time() - start_time
    ipk3_size = os.path.getsize(DEST_FILENAME) / 1048576
    logg('Generated %s (%.2f MiB) with %s maps in %s episodes in %.2f seconds.' % (DEST_FILENAME, ipk3_size, num_maps, num_eps, elapsed_time))
    logg('Done!')
    if num_errors > 0:
        logg('%s errors found, see %s for details.' % (num_errors, LOG_FILENAME))
    input('Press Enter to exit.\n')
    clear_temp()
    logfile.close()

if __name__ == "__main__":
    main()
