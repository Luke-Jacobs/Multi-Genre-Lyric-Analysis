from collections import Counter
from bs4 import BeautifulSoup
import pickle, os.path, re, requests, time
from matplotlib import pyplot as plt
import numpy as np
from sklearn.decomposition import PCA
import matplotlib.patches as mpatches
import argparse

class Utilities:

    @staticmethod
    def urlify(s: str) -> str:
        """Take a normal string and convert it to an AZlyrics url format"""
        s = s.lower().replace(" ", "")
        regex = re.compile('[^a-z0-9]')
        s = regex.sub("", s)
        return s

    @staticmethod
    def removeBadCharacters(s: str) -> str:
        """Remove characters that are outside the range of ASCII"""
        byteStr = [ord(char) for char in s if ord(char) < 128]
        return bytes(byteStr).decode()

    @staticmethod
    # get files with extension in a certain directory
    # files are relative paths
    def getFilesWithExtOnPath(path: str, targetExt: str):
        """Get a list of paths to files with a specified extension on a specified path"""
        fileList = []
        for subdir, dirs, files in os.walk(path):
            for name in files:
                ext = os.path.splitext(name)[1]  # get extension to filter files
                if ext == targetExt:
                    fileList.append(os.path.join(subdir, name))
        return fileList

    @staticmethod
    def writeIterable(obj, filename):
        """Write an iterable to a file in a visually-appealing way."""
        with open(filename, "w") as fp:
            for item in obj:
                fp.write(str(item) + "\n")


class Song:

    GENERIC_SONG_URL = 'https://www.azlyrics.com/lyrics/%s/%s.html'  # To be filled by methods
    FAILED_DOWNLOAD_TAG = "NaN"  # self.lyrics is set to this value if the lyrics cannot be downloaded from AZlyrics

    def __init__(self):
        self.title = ""  # Song title
        self.lyrics = ""  # Contents of lyrics in string form
        self.wordCount = None  # Counter object that will store word frequencies

        self.artist = ""
        self.album = ""

    def setLyrics(self, title, lyrics):
        self.title = title
        self.lyrics = lyrics

    def __str__(self):
        """Returns the lyric content of this song."""
        return self.lyrics

    def getDescription(self):
        return "%s by %s from %s" % (self.title, self.artist, self.album)

    def getWordCount(self):
        """Calculates word frequency and sets self.word_freq to a Counter object"""
        if not self.wordCount:
            words = Counter()
            words.update(self.lyrics.split())
            self.wordCount = words
        return self.wordCount

    def getVocabulary(self):
        """Calculates unique words used in lyrics"""
        return set(self.getWordCount())

    def download(self, artist: str, show=True, override=False) -> bool:
        """Given artist and title, download the lyrics of this song from AZlyrics."""

        if not (self.title and artist):  # Throw error if one of these is undefined
            raise RuntimeError("Song: Downloading without knowledge of song title or artist")

        if self.lyrics and not override:  # If no caller override and we already have lyrics downloaded in the object
            return False  # No need to download if we already have lyrics

        titlepath = Utilities.urlify(self.title)
        artistpath = Utilities.urlify(artist)

        url = Song.GENERIC_SONG_URL % (artistpath, titlepath)

        if show:
            print("Downloading (%s)" % url)

        page = requests.get(url)
        if page.status_code == 200:
            self.setLyricsFromHTML(page.text)
            return True
        else:
            self.lyrics = "NaN"  # Constant to use if something went wrong
            return False

    @staticmethod
    def restoreFromPath(path):
        """Retrieve a song object from a local file indicated by a path."""
        with open(path, "rb") as fp:
            song = pickle.load(fp)
        return song

    @staticmethod
    def getSongFromURL(artist_url, title_url):
        """Fills out the self.lyrics variable given self.artist and self.title"""
        # Url follows this pattern: https://www.azlyrics.com/lyrics/[artist urlname]/[title].html
        song = Song()
        url = Song.GENERIC_SONG_URL % (artist_url, title_url)
        page = requests.get(url)
        if page.status_code == 200:
            song.setLyricsFromHTML(page.text)
            return song
        else:
            raise RuntimeError("Downloading Song Page: Status Code not 200")

    @staticmethod
    def cleanLyrics(lyrics: str) -> str:
        """Remove characters and phrases that we don't want to include in our dataset."""
        badCharacters = ["(", ")", "\'", "\'", ","]
        separationCharacters = ["\n\r", "\r\n", "  "]
        for char in badCharacters:
            lyrics = lyrics.replace(char, "")
        for char in separationCharacters:
            lyrics = lyrics.replace(char, " ")
        lyrics = Utilities.removeBadCharacters(lyrics)
        lyrics = lyrics.lower()

        # Manipulating chorus indicators in lyric data
        chorRef = "[chorus]"  # A constant that indicates that a chorus is referenced
        chorDef = "[chorus:]"  # A chorus definition in the AZlyrics format
        if lyrics.find(chorRef) + 1:  # If we found a reference
            if lyrics.find(chorDef) + 1:  # If we found a definition
                start = lyrics.find(chorDef) + len(chorDef)
                end = lyrics[start:].find("\n\n") + start
                chorStr = lyrics[start:end]  # This is the string that holds our chorus
            else:
                print("[-] Chorus reference but no chorus definition")
                chorStr = ""  # If we did not find a chorus
            lyrics = lyrics.replace(chorRef, chorStr)
        lyrics = re.sub(r'\[[^\]]*\]', '', lyrics)

        lyrics = re.sub(r'[?!@#$%^&*().]', '', lyrics)
        return lyrics

    @staticmethod
    def __cleanBracketExpressions(lyrics: str) -> str:
        chorRef = "[chorus]"
        chorDef = "[chorus:]"
        if lyrics.find(chorRef) + 1:  # if reference
            if lyrics.find(chorDef) + 1:  # if definition
                start = lyrics.find(chorDef) + len(chorDef)
                end = lyrics[start:].find("\n\n") + start
                chorStr = lyrics[start:end]
                # print("Found chorus: %s" % chorStr)
            else:
                print("[-] Chorus ref but no def")
                chorStr = ""
            lyrics = lyrics.replace(chorRef, chorStr)

        lyrics = re.sub(r'\[[^\]]*\]', '', lyrics)
        return lyrics

    def setLyricsFromHTML(self, page: str):
        """Set self.lyrics to lyrics from an azlyrics html string"""
        # Get lyrics section from website string
        doc = BeautifulSoup(page, 'html.parser')
        lyrics = doc.find("body")
        lyrics = lyrics.find("div", attrs={"class": "container main-page"})
        lyrics = lyrics.find("div", attrs={"class": "row"})
        lyrics = lyrics.find("div", attrs={"class": "col-xs-12 col-lg-8 text-center"})
        lyrics = lyrics.findAll("div")[6].text
        # Clean lyrics for analysis
        lyrics = Song.cleanLyrics(lyrics)
        self.lyrics = lyrics

    def save(self):
        if not (self.artist and self.album and self.title):
            raise RuntimeError("Lyric saving: artist/album/title not initialized")

        path = os.path.join("Saved Song", self.artist, self.album, self.title) + ".song"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb+") as fp:
            pickle.dump(self, fp)


class Album:

    def __init__(self):
        self.title = ""  # Album title
        self.artist = ""  # Artist name
        self.year = 0  # Album year
        self.songs = []  # List of album Songs
        self.wordCount = None

    def __str__(self):
        return self.title

    def getSongFromTitle(self, songTitle: str):
        """Return a Song object given a song's title."""
        for song in self.songs:
            if song.title == songTitle:
                return song
        return None

    def getWordCount(self):
        """Return a Counter object from this Album."""
        self.wordCount = Counter()
        for song in self.songs:
            self.wordCount += song.getWordCount()
        return self.wordCount

    def getWordsetCount(self, wordset: list):
        """Given a list of words (str), return the frequency of these words in this album."""
        freq = 0.0
        wc = self.getWordCount()
        for word in wordset:
            freq += wc[word]  # Add up occurences of each word
        totalOccurences = sum(list(wc.values()))
        if totalOccurences > 0:
            freq /= totalOccurences  # Divide occurences by total words
            return freq
        else:
            return 0.0

    def getVocabulary(self):
        """Return the set of words that this Album uses."""
        vocab = set()
        for song in self.songs:
            vocab.update(song.getVocabulary())
        return vocab

    def getNsongs(self):
        return len(self.songs)

    def getSongList(self):
        return self.songs

    def downloadAll(self, delay=8):
        """Download the lyrics to every song in this Album."""
        for song in self.songs:
            if not song.download(self.artist):  # Download song's lyrics
                print("Already downloaded song lyrics")
                continue  # Move on if that song is already downloaded
            else:
                time.sleep(delay)


class Artist:
    """Artist type includes Albums and an artist name.
    Its main use is to creates Song types given an artist URL."""

    def __init__(self):
        self.name = ""  # Artist name
        self.albums = []  # List of Albums
        self.count = None  # For word count

    def __str__(self):
        """TODO"""
        return self.name

    @staticmethod
    def fromName(name, show=True):
        # To URL string form
        artistPath = Utilities.urlify(name)

        # Get artist main page
        artistURL = "https://www.azlyrics.com/" + artistPath[0] + "/" + artistPath + ".html"
        if show:
            print("Downloading (%s)" % artistURL)
        artistPage = requests.get(artistURL)
        if artistPage.status_code != 200:
            raise RuntimeError("Artist: failed to grab artist page (not 200 status)")

        doc = BeautifulSoup(artistPage.text, 'html.parser')
        albumHTML = doc.find("body")
        albumHTML = albumHTML.find("div", attrs={"class": "container main-page"})
        albumHTML = albumHTML.find("div", attrs={"class": "row"})
        albumHTML = albumHTML.find("div", attrs={"class": "col-xs-12 col-md-6 text-center"})
        albumHTML = albumHTML.find("div", id="listAlbum")  # section with album titles and songs

        albumProperties = albumHTML.findAll("div", attrs={"class": "album"})
        albums = []  # THis will be a list of Albums (name, year, songs)

        # Populate "albums" with Album objects without songs filled out
        for albumProperty in albumProperties:
            if albumProperty.text.find("other songs") + 1:
                albumText = "album: \"Other\" (0)"
            else:
                albumText = albumProperty.text

            albumName = re.search("\"(.*)\"", albumText)
            albumName = albumName.group(1)

            year = re.search("\((.*)\)", albumText)
            year = year.group(1)

            newAlbum = Album()
            newAlbum.title = albumName
            newAlbum.artist = name
            try:
                newAlbum.year = int(year)
            except ValueError:
                newAlbum.year = 0

            albums.append(newAlbum)

        # Match songs with albums
        albumIDsAndSongLinks = albumHTML.findAll("a")
        albumN = -1  # assume album id is the 1st item
        for idOrLink in albumIDsAndSongLinks:
            if idOrLink.attrs.get("id"):  # if album indicator
                albumN += 1  # Move on to the next album
            elif idOrLink.attrs.get("href"):  # if song indicator
                newSong = Song()
                newSong.title = idOrLink.text
                albums[albumN].songs.append(newSong)  # append Song object to specific album
            else:
                raise RuntimeError("Artist: Song page is formatted incorrectly")

        # Build final object
        output = Artist()
        output.name = name
        output.albums = albums

        return output  # Return Artist object

    def getAlbumFromTitle(self, albumTitle: str):
        for album in self.albums:
            if album.title == albumTitle: #if we found a matching album
                return album
        return None #no albums were found with that title

    def getWordCount(self):
        if self.count:
            return self.count
        self.count = Counter()
        for album in self.albums:
            self.count += album.getWordCount()
        return self.count

    def getWordsetCount(self, wordset):
        freq = 0.0
        wc = self.getWordCount()
        for word in wordset:
            freq += wc[word] #add up occurences of each word
        freq /= sum(list(wc.values())) #divide by total words
        return freq

    def getVocabulary(self):
        vocab = set()
        for album in self.albums:
            vocab.update(album.getVocabulary())
        return vocab

    def getNsongs(self):
        albums = [album.getNsongs() for album in self.albums]
        return sum(albums)

    def getSongList(self):
        return [song for album in self.albums for song in album.songs] #return a 1d list of artist's songs

    def getAlbums(self):
        return self.albums

    def downloadAll(self, delay=8):
        for album in self.albums:
            album.downloadAll(delay)

    def save(self, filename):
        with open(filename, "wb+") as fp:
            pickle.dump(self, fp)

    @staticmethod
    def restore(filename):
        with open(filename, "rb") as fp:
            obj = pickle.load(fp)
        return obj


class Genre:

    def __init__(self, title="", artists=[]):
        self.artists = artists
        self.title = title
        self.wordCount = None

    def __str__(self):
        return self.title

    #For combining genres with the same name - symbol <
    def __lt__(self, other):
        if self.title != other.title:
            raise Warning("Title mismatch when combining (%s) and (%s)" % (self.title, other.title))
        self.artists += other.artists

    @staticmethod
    def fromArtistList(artistList: list, delay=5):
        artistObjects = []
        for artist in artistList:
            artistObjects.append(Artist.fromName(artist))
            time.sleep(delay)
        obj = Genre()
        obj.artists = artistObjects
        return obj

    @staticmethod
    def fromRawHTML(htmlFolder: str):
        # Object we are building
        out = Genre()
        # Get files with .raw ending and iterate through them
        lyricFiles = Utilities.getFilesWithExtOnPath(htmlFolder, ".raw")
        for filename in lyricFiles:
            # Get elements in filename
            artist, albumStr, songStr = filename.split("\\")[1::]

            # Get artist object if initialized
            artistObj = out.getArtistFromName(artist)

            if not artistObj:
                artistObj = Artist()
                artistObj.name = artist
                out.artists.append(artistObj)

            # Get album object if initialized
            albumTitle = ' '.join(albumStr.split(" ")[:-1:])  # remove (year) from the end of the folder name
            albumObj = artistObj.getAlbumFromTitle(albumTitle)

            if not albumObj:
                year = re.search("\((.*)\)", albumStr)
                year = int(year.group(1))
                albumObj = Album()
                albumObj.title = albumTitle
                albumObj.artist = artist
                albumObj.year = year
                artistObj.albums.append(albumObj)

            # Make new song object
            newSong = Song()
            songTitle = os.path.splitext(songStr)[0]
            newSong.title = songTitle

            # Open and read the raw HTML file
            with open(filename, "rb") as fp:
                rawcontent = fp.read()
            lyricContent = bytes([char for char in rawcontent if char < 128]).decode()
            newSong.setLyricsFromHTML(lyricContent)
            albumObj.songs.append(newSong) #add Song
        return out

    @staticmethod
    def restore(filename):
        with open(filename, "rb") as fp:
            obj = pickle.load(fp)
        return obj

    @staticmethod
    def downloadOverTime(title: str, artistList: list, filename: str):
        # Get obj initialized
        if os.path.exists(filename + " - Error"):
            workingGenre = Genre.restore(filename + " - Error")
        else:
            workingGenre = Genre.fromArtistList(artistList)
            workingGenre.title = title
        # Download
        try:
            workingGenre.downloadAll()
        except Exception as e:
            print("Error: %s" % str(e))
            workingGenre.save(filename + " - Error")
            raise e
        workingGenre.save(filename)
        return True

    def getArtistFromName(self, artistName):
        for artist in self.artists:
            if artist.name == artistName:
                return artist
        return None

    def getWordCount(self):
        if self.wordCount:
            return self.wordCount

        self.wordCount = Counter()
        for artist in self.artists:
            self.wordCount += artist.getWordCount()
        return self.wordCount

    def getVocabulary(self):
        vocab = set()
        for artist in self.artists:
            vocab.update(artist.getVocabulary())
        return vocab

    def getNsongs(self):
        artists = [artist.getNsongs() for artist in self.artists]
        return sum(artists)

    def getSongList(self):
        return [song for artist in self.artists for song in artist.getSongList()]

    def downloadAll(self, delay=10):
        for artist in self.artists:
            artist.downloadAll(delay)

    def save(self, filename):
        with open(filename, "wb+") as fp:
            pickle.dump(self, fp)

    # Analysis
    def comparedTo(self, otherGenre, show=True):
        myVocab = self.getVocabulary()
        otherVocab = otherGenre.getVocabulary()

        similarVocab = myVocab.intersection(otherVocab)
        differentVocab = myVocab.difference(otherVocab)

        if show:
            print("Vocab 1: %d\nVocab 2: %d\n" % (len(myVocab), len(otherVocab)))
            print("Similar vocabulary: %d\nDifferent vocabulary: %d" % (len(similarVocab), len(differentVocab)))

        return {"Same": similarVocab, "Different": differentVocab}


class Collection:
    """
    Used for storing many songs from many genres
    """

    def __init__(self):
        self.genres = [] #List of Genre objects

    @staticmethod
    #Pulls together many Genre obj files into a Collection obj
    def fromGenreFiles(genreFilenameList: list, genreTitlesList=None):
        obj = Collection()
        for i, file in enumerate(genreFilenameList):
            g = Genre.restore(file)
            if genreTitlesList: #if caller defines what to title each genre
                g.title = genreTitlesList[i]
            #In case there are multiple Genre obj files with the same name
            existingGenre = obj.getGenreFromTitle(g.title)
            if existingGenre:
                existingGenre < g #Give g's artists to the genre in the collection
            else:
                obj.genres.append(g)
        return obj

    @staticmethod
    def restore(filename: str):
        with open(filename, "rb") as fp:
            obj = pickle.load(fp)
        return obj

    def save(self, filename: str) -> None:
        with open(filename, "wb") as fp:
            pickle.dump(self, fp)

    #Adds individual Artist to collection
    def add(self, artist: Artist, genreTitle: str):
        existingGenre = self.getGenreFromTitle(genreTitle)
        if not existingGenre:
            newGenre = Genre(title=genreTitle, artists=[artist])
            self.genres.append(newGenre)
        else:
            existingGenre.artists.append(artist)

    def remove(self, artistName: str):
        for genre in self.genres:
            artist = genre.getArtistsFromNames(artistName)
            if artist: #if found him/her obj
                genre.artists.remove(artist)

    #Downloads many artists and adds them to respective genres
    def downloadArtistsFromList(self, listfile: str) -> None:
        with open(listfile, "r") as fp:
            # For each artist - genreTitle pair
            for line in fp:
                # Download Artist obj
                artistName, genreTitle = line.replace("\n", "").split(" - ")
                artist = Artist.fromName(artistName)
                artist.downloadAll()
                # Add Artist to our collection by creating/appending to a new/existing Genre obj
                self.add(artist, genreTitle)

    #Retrieves Genre obj given its title
    def getGenreFromTitle(self, title):
        for genre in self.genres:
            if genre.title == title:
                return genre
        return None


class Analysis:
    """
    Analytical functions to use with Collection objects
    """

    @staticmethod
    def graphGenresWithPCA(genres: list, xName=None, yName=None,
                           title=None, returnVectors=False):
        """Graph Artists in a scatterplot using PCA to reduce word count dimensions."""

        # Order our data
        allArtists = [artist for genre in genres for artist in genre.artists]  # List of Artist objs
        orderedNames = [artist.name for artist in allArtists]  # Artist names in order

        # Collect all artists' vocabulary
        allVocab = set()
        for artist in allArtists:
            voc = artist.getVocabulary()
            allVocab.update(voc)
        allVocab = list(allVocab)  # List of all vocab words among genres: ['A', 'B', ...] -

        # Fancy graph variables for color and a legend
        nodeColor = ['purple']*len(allArtists)  # The default color is purple
        colors = ['red', 'green', 'blue', 'yellow', 'orange', 'purple']
        legendData = []

        artistsWordVectors = [[None]]*len(allArtists)
        for i in range(len(genres)):
            genreColor = colors[i]
            for artist in genres[i].artists:  # Get word vectors for every artist to process by PCA
                wordVector = []  # Fixed length vector: [7, 6, 34, ...]
                wordCount = artist.getWordCount()
                for vocabWord in allVocab:
                    wordVector.append(wordCount[vocabWord])
                index = orderedNames.index(artist.name)
                artistsWordVectors[index] = wordVector
                nodeColor[index] = genreColor
            legendData.append(mpatches.Patch(color=genreColor, label=genres[i].title))  # Add new genre to legend

        # PCA on artist vectors
        pca = PCA(n_components=2).fit(artistsWordVectors)  # Setup and fit our model
        data2D = pca.transform(artistsWordVectors)  # Use model to reduce long vectors to 2d vectors

        # Graph PCA results
        ax = plt.axes()
        ax.axis('equal')  # Force graph zoom to be proportional - x and y scale are the same
        ax.scatter(data2D[:, 0], data2D[:, 1], c=nodeColor)  # Plot our PCA points with corresponding color data
        ax.legend(handles=legendData)
        for i, name in enumerate(orderedNames):  # Assign
            ax.annotate(name, (data2D[i, 0]+1, data2D[i, 1]+1))
        if xName:  # If caller specifies x-axis title
            ax.set_xlabel(xName)
        if yName:  # If caller specifies y-axis title
            ax.set_ylabel(yName)
        if title:  # If caller specifies graph title
            ax.set_title(title)
        plt.show()

        # Return results
        if returnVectors:  # If the caller wants data to return
            return artistsWordVectors, data2D
        else:
            return None

    @staticmethod
    def graphGenresByWordsets(genres: list, wordsetX: list, wordsetY: list,
                              xName=None, yName=None, showArtistNames=True):
        """Graph artists in a scatterplot with genre-based coloring.
        Each artist's position is determined by their vocabulary's frequency
        of 2 wordsets, for the X and Y axis."""

        colors = ['red', 'green', 'blue', 'yellow', 'orange', 'purple']
        artistsLoc = []
        artistsName = []  # list of artist names
        artistsColor = []  # list of node colors
        legendPatches = []  # list for legend

        # Generate our graph data from each Artist object
        for i, genre in enumerate(genres):
            currentColor = colors[i]
            legendPatches.append(mpatches.Patch(color=currentColor, label=genre.title))
            for artist in genre.artists:  # add points to empty lists
                xfreq = artist.getWordsetCount(wordsetX)
                yfreq = artist.getWordsetCount(wordsetY)
                artistsLoc.append((xfreq, yfreq))
                artistsName.append(artist.name)
                artistsColor.append(currentColor)

        # Graph it!
        data = np.array(artistsLoc, dtype=float)
        ax = plt.axes()
        ax.scatter(data[:, 0], data[:, 1], c=artistsColor)
        ax.axis('equal')
        ax.legend(handles=legendPatches)

        # Extra options for graphing
        if showArtistNames:
            for i, name in enumerate(artistsName):
                ax.annotate(name, (data[i, 0], data[i, 1]))
        if xName:
            ax.set_xlabel(xName)
        if yName:
            ax.set_ylabel(yName)

        plt.show()

    @staticmethod
    def graphWordsetOverTime(wordset: list, genres=None, artists=None,
                             xName=None, yName=None, title=None):
        """Show a line graph of the evolution of either genres or artists over time.
        Each point on the graph is an average frequency of the wordset at that moment
        in time."""

        legendData = []
        # Main data collection
        fig, ax = plt.subplots()

        # If the caller wants to graph the evolution of individual *genres* over time
        # TODO Make clearer
        if genres:
            for i, genre in enumerate(genres):
                yearFreqDict = {}  # Years that an album in this genre was released -> freq of wordset

                # Collect a list of Genre objs in ascending order by year
                for artist in genre.artists:
                    for album in artist.albums:
                        if album.year == 0:
                            continue
                        if not album.year in yearFreqDict: #if new year for an album
                            yearFreqDict[album.year] = [album.getWordsetCount(wordset), 1] #the 1 is used for averages
                        yearFreqDict[album.year][0] += album.getWordsetCount(wordset)
                        yearFreqDict[album.year][1] += 1 #add 1 to the final divisor to calculate an avg
                for year in yearFreqDict:
                    yearFreqDict[year] = yearFreqDict[year][0] / yearFreqDict[year][1]  # calculate avg

                # Plot this genre's data
                dataPoints = list(yearFreqDict.items())
                dataPoints.sort(key=lambda x: x[0])  # Sort by year value (x)
                xVals = [item[0] for item in dataPoints]
                yVals = [item[1] for item in dataPoints]
                legendData.append(ax.plot(xVals, yVals, label=genre.title)[0])

        # If the caller wants to graph the evolution of multiple *artists* over time
        if artists:
            for i, artist in enumerate(artists):
                yearFreqDict = {}  # Years that an album by this artist was released -> freq of wordset
                for album in artist.albums:
                    if album.year == 0:
                        continue
                    if album.year not in yearFreqDict:  # if new year for an album
                        yearFreqDict[album.year] = album.getWordsetCount(wordset)
                        continue
                    yearFreqDict[album.year] += album.getWordsetCount(wordset)
                    yearFreqDict[album.year] /= 2.0  # Average value for

                # Plot this genre's data
                dataPoints = list(yearFreqDict.items())
                dataPoints.sort(key=lambda x: x[0])  # sort by year value (x)
                xVals = [item[0] for item in dataPoints]
                yVals = [item[1] for item in dataPoints]
                legendData.append(ax.plot(xVals, yVals, label=artist.name)[0])

        # Graph parameters
        ax.legend(handles=legendData)
        if xName:
            ax.set_xlabel(xName)
        if yName:
            ax.set_ylabel(yName)
        if title:
            ax.set_title(title)
        plt.show()

    @staticmethod
    def rankByWordsetFrequency(lyricObjects: list, wordset: list) -> list:
        """Return a ranking of artists based on the frequency their vocabulary uses the words in the wordset."""
        # [Artist name -> [Year -> Percent (float)]]
        #   Rank ascending year -> Word Count of self pronouns

        # TODO
        ranking = []
        for lyricObject in lyricObjects:
            ranking.append(lyricObject)

        totalResults = {}
        for lyricObject in lyricObjects:
            results = {}  # dictionary of year -> word count of self pronouns
            for album in lyricObject.albums:
                year = album.year
                if not year:  # if year 0, move on
                    continue
                wordCount = album.getWordCount()  # all words
                totalWords = sum(wordCount.values())
                selectedWordPercent = 0.0  # selected words
                for word in wordset:
                    freq = wordCount.get(word)
                    if freq:
                        selectedWordPercent += freq  # add occurences

                if results.get(year):
                    results[year] += (selectedWordPercent / 2.0 / totalWords)
                else:
                    results[year] = selectedWordPercent / totalWords
            totalResults[lyricObject.name] = results

        rankingByWordset = []
        for artist in totalResults:
            yVals = [totalResults[artist][year] for year in totalResults[artist]]
            avg = sum(yVals) / len(yVals)
            rankingByWordset.append((artist, avg))
        rankingByWordset.sort(key=lambda x: x[1])
        for artist in rankingByWordset:
            print(artist[0])

        # Plot
        for artist in totalResults:
            xVals = list(totalResults[artist].keys())
            yVals = [totalResults[artist][year] for year in totalResults[artist]]
            print(xVals, "\n", yVals)

            index = np.arange(len(xVals))
            fig, ax = plt.subplots()
            ax.bar(xVals, yVals)
            ax.set_title(artist)
            ax.set_xlabel('Years')
            ax.set_ylabel('Frequency of selfish pronouns')
            # ax.set_xticks(index, xVals)
            fig.tight_layout()
            plt.show()

    @staticmethod
    def getUniqueVocabOfTarget(target, others: list) -> set:
        """Returns the difference of target's vocab and the collective vocab of others.
        "Target" and "others" can be a Song, Album, Artist, or Genre."""
        targetVocab = target.getVocabulary()
        otherVocab = set()  # The set of the vocabulary from each other
        for other in others:
            otherVocab.update(other.getVocabulary())
        return targetVocab.difference(otherVocab)  # Return unique vocab

    @staticmethod
    def compareArtistToOthers(artist: Artist, others: list) -> dict:
        """Return a dictionary of [other artist]: [vocab similarities] for a given artist."""
        comparisons = {}
        for other in others:
            if other is artist:
                continue
            # Get n of similarities
            selfVoc = artist.getVocabulary()
            otherVoc = other.getVocabulary()
            comparisons[other.name] = len(selfVoc.intersection(otherVoc))
        return comparisons  # Dictionary {artistName: similarity score}


selfPronouns = ["me", "my", "mine"]
collectivePronouns = ["we", "our", "us"]
otherPronouns = ["you", "your", "he", "she", "his", "her", "they", "them"]


def parseInputs():
    args = argparse.ArgumentParser(description='A program to download and analyze lyrics')
    args.add_argument('mode', type=str,
                      help='The mode of program function, either download, graph, or rank')

    # Download args
    args.add_argument('-o', '--delay', help='The file to store the downloaded lyric data')
    args.add_argument('-i', '--input', help='The file that contains a list of artists to download')
    args.add_argument('-d', '--delay', help='Delay of the downloader for each song')

    # Graphing args
    args.add_argument('--data', required=False,
                      help='The collection that is the input to the graphical analysis')

    args.add_argument('-pca', required=False, default=False, action="store_true",
                      help='Use Principle Component Analysis to graph artists')
    args.add_argument('-scatter', required=False, type=bool, default=False,
                      help='Make a scatterplot')
    args.add_argument('-x', required=False, type=list,
                      help='X axis wordset')

    args = args.parse_args()

    if args.mode == 'download':  # If the user wants to download some lyrics
        pass
    elif args.mode == 'graph':  # If the user wants to use stats to graph lyric data
        pass
    elif args.mode == 'rank':  # If the user wants to rank songs/albums/artists/genres on certain criteria
        pass
    else:
        print('Unknown mode')
        return -1


if __name__ == "__main__":
    # parseInputs()
    mc = Collection.restore("Music Collection")

    Analysis.rankArtistsByWordSet(mc.genres[0].artists, ["the"])
    exit(0)
    # mc = Collection.restore("Music Collection - Failed")
    # try:
    #     mc.downloadArtistsFromList("Artist List.txt")
    # except Exception as e:
    #     print(e)
    #     mc.save("Music Collection - Failed")
    #     exit(-1)
    # mc.save("Music Collection - Updated")


    raw, processed = Analysis.graphGenresWithPCA(mc.genres, xName='Principle Component 1 (correlated with size)',
                                yName='Principle Component 2', title='Artist vocabulary clustered by similarity',
                                returnVectors=True)

    Utilities.writeIterable(raw, "RawArtistVectors.txt")
    Utilities.writeIterable(processed, "ProcessedPCAVectors.txt")
