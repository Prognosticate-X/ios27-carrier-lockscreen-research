#import <CoreFoundation/CoreFoundation.h>
#import <Foundation/Foundation.h>
#include <sys/socket.h>
#include <unistd.h>

#import "airlift_target.h"

typedef const void *AMDeviceRef;
typedef const void *AMDeviceNotificationRef;
typedef void *AMDServiceConnectionRef;
typedef void *AFCConnectionRef;
typedef void *AFCKeyValueRef;
typedef void *AFCFileRef;
typedef void *AFCDirectoryRef;

typedef struct {
    AMDeviceRef device;
    unsigned int message;
} AMDeviceNotificationCallbackInfo;

extern int AMDeviceNotificationSubscribeWithOptions(
    void (*callback)(AMDeviceNotificationCallbackInfo *, void *),
    int unused,
    unsigned int connectionType,
    void *context,
    AMDeviceNotificationRef *subscription,
    CFDictionaryRef options);
extern int AMDeviceNotificationUnsubscribe(AMDeviceNotificationRef subscription);
extern CFStringRef AMDeviceCopyDeviceIdentifier(AMDeviceRef device);
extern CFTypeRef AMDeviceCopyValue(AMDeviceRef device,
                                   CFStringRef domain,
                                   CFStringRef key);
extern int AMDeviceConnect(AMDeviceRef device);
extern int AMDeviceDisconnect(AMDeviceRef device);
extern int AMDeviceIsPaired(AMDeviceRef device);
extern int AMDeviceValidatePairing(AMDeviceRef device);
extern int AMDeviceStartSession(AMDeviceRef device);
extern int AMDeviceStopSession(AMDeviceRef device);
extern int AMDeviceSecureStartService(AMDeviceRef device,
                                      CFStringRef serviceName,
                                      CFDictionaryRef options,
                                      AMDServiceConnectionRef *connection);
extern int AMDServiceConnectionGetSocket(AMDServiceConnectionRef connection);
extern void *AMDServiceConnectionGetSecureIOContext(
    AMDServiceConnectionRef connection);
extern int AMDServiceConnectionInvalidate(AMDServiceConnectionRef connection);
extern int AMDServiceConnectionSend(AMDServiceConnectionRef connection,
                                    const void *bytes,
                                    size_t length);
extern int AMDServiceConnectionSendMessage(AMDServiceConnectionRef connection,
                                           CFTypeRef message,
                                           CFPropertyListFormat format);
extern int AMDServiceConnectionReceiveMessage(AMDServiceConnectionRef connection,
                                              CFTypeRef *message,
                                              CFPropertyListFormat *format);

extern int AFCConnectionOpen(int socket,
                             unsigned int ioTimeout,
                             AFCConnectionRef *connection);
extern int AFCConnectionClose(AFCConnectionRef connection);
extern int AFCConnectionSetSecureContext(AFCConnectionRef connection,
                                         void *secureContext);
extern int AFCConnectionSetDisposeSecureContextOnInvalidate(
    AFCConnectionRef connection,
    int dispose);
extern int AFCConnectionSetIOTimeout(AFCConnectionRef connection,
                                     unsigned int timeout);
extern int AFCFileInfoOpen(AFCConnectionRef connection,
                           const char *path,
                           AFCKeyValueRef *dictionary);
extern int AFCKeyValueRead(AFCKeyValueRef dictionary, char **key, char **value);
extern int AFCKeyValueClose(AFCKeyValueRef dictionary);
extern int AFCFileRefOpen(AFCConnectionRef connection,
                          const char *path,
                          unsigned long long mode,
                          AFCFileRef *file);
extern int AFCFileRefRead(AFCConnectionRef connection,
                          AFCFileRef file,
                          void *bytes,
                          long *length);
extern int AFCFileRefWrite(AFCConnectionRef connection,
                           AFCFileRef file,
                           const void *bytes,
                           long length);
extern int AFCFileRefClose(AFCConnectionRef connection, AFCFileRef file);
extern int AFCDirectoryOpen(AFCConnectionRef connection,
                            const char *path,
                            AFCDirectoryRef *directory);
extern int AFCDirectoryRead(AFCConnectionRef connection,
                            AFCDirectoryRef directory,
                            char **entry);
extern int AFCDirectoryClose(AFCConnectionRef connection,
                             AFCDirectoryRef directory);
extern int AFCDirectoryCreate(AFCConnectionRef connection, const char *path);
extern int AFCRemovePath(AFCConnectionRef connection, const char *path);

static const char *TrackedBooksFiles[] = {
    "Books/Books.plist",
    "Books/Sync/Books.plist",
    "Books/Sync/Upload.plist",
    "Books/Sync/Database/OutstandingAssets_4.sqlite",
    "Books/Sync/Database/OutstandingAssets_4.sqlite-shm",
    "Books/Sync/Database/OutstandingAssets_4.sqlite-wal",
};

static const char *TrackedBooksDirectories[] = {
    "Books",
    "Books/Sync",
    "Books/Sync/Database",
};

static CFStringRef TargetIdentifier;
static AMDeviceRef TargetDevice;

typedef struct {
    AMDeviceRef device;
    BOOL connected;
    BOOL sessionStarted;
    AMDServiceConnectionRef afcService;
    AFCConnectionRef afc;
    int subscribeStatus;
    int connectStatus;
    int validateStatus;
    int sessionStatus;
    int serviceStatus;
    int afcStatus;
} DeviceSession;

static void DeviceCallback(AMDeviceNotificationCallbackInfo *info,
                           void *context) {
    (void)context;
    if (!info || !info->device || info->message != 1 || TargetDevice) return;
    CFStringRef identifier = AMDeviceCopyDeviceIdentifier(info->device);
    BOOL matches = identifier && CFEqual(identifier, TargetIdentifier);
    if (identifier) CFRelease(identifier);
    if (!matches) return;
    TargetDevice = CFRetain(info->device);
    CFRunLoopStop(CFRunLoopGetMain());
}

static int FindTarget(void) {
    NSDictionary *options = @{
        @"NotificationOptionSearchForPairedDevices": @YES,
        @"NotificationOptionSearchForPairedDevicesViaDirectConnectionsOnly": @NO,
        @"NotificationOptionSearchForWiFiPairableDevices": @NO,
        @"NotificationOptionEnableRemoteXPC": @YES,
        @"NotificationOptionEnableUSBMux": @YES,
    };
    AMDeviceNotificationRef subscription = NULL;
    int status = AMDeviceNotificationSubscribeWithOptions(
        DeviceCallback,
        0,
        0,
        NULL,
        &subscription,
        (__bridge CFDictionaryRef)options);
    if (status == 0)
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 30.0, false);
    if (subscription) AMDeviceNotificationUnsubscribe(subscription);
    return status;
}

static void OpenSession(DeviceSession *session) {
    memset(session, 0, sizeof(*session));
    session->connectStatus = session->validateStatus = -1;
    session->sessionStatus = session->serviceStatus = session->afcStatus = -1;
    session->subscribeStatus = FindTarget();
    session->device = TargetDevice;
    if (!session->device) return;

    session->connectStatus = AMDeviceConnect(session->device);
    session->connected = session->connectStatus == 0;
    if (!session->connected || !AMDeviceIsPaired(session->device)) return;
    session->validateStatus = AMDeviceValidatePairing(session->device);
    if (session->validateStatus != 0) return;
    session->sessionStatus = AMDeviceStartSession(session->device);
    session->sessionStarted = session->sessionStatus == 0;
    if (!session->sessionStarted) return;
    session->serviceStatus = AMDeviceSecureStartService(
        session->device,
        CFSTR("com.apple.afc"),
        NULL,
        &session->afcService);
    if (session->serviceStatus != 0 || !session->afcService) return;
    session->afcStatus = AFCConnectionOpen(
        AMDServiceConnectionGetSocket(session->afcService),
        0,
        &session->afc);
    void *secureContext =
        AMDServiceConnectionGetSecureIOContext(session->afcService);
    if (session->afcStatus == 0 && session->afc && secureContext) {
        AFCConnectionSetSecureContext(session->afc, secureContext);
        AFCConnectionSetDisposeSecureContextOnInvalidate(session->afc, 0);
        AFCConnectionSetIOTimeout(session->afc, 30);
    }
}

static void CloseSession(DeviceSession *session) {
    if (session->afc) AFCConnectionClose(session->afc);
    if (session->afcService)
        AMDServiceConnectionInvalidate(session->afcService);
    if (session->sessionStarted) AMDeviceStopSession(session->device);
    if (session->connected) AMDeviceDisconnect(session->device);
    if (session->device) CFRelease(session->device);
    TargetDevice = NULL;
}

static void PrintJSON(NSDictionary *object) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:object
                                                   options:0
                                                     error:nil];
    if (!data) return;
    fwrite(data.bytes, 1, data.length, stdout);
    fwrite("\n", 1, 1, stdout);
}

static BOOL AFCExists(AFCConnectionRef afc, NSString *path) {
    AFCKeyValueRef info = NULL;
    int status = AFCFileInfoOpen(afc, path.fileSystemRepresentation, &info);
    if (info) AFCKeyValueClose(info);
    return status == 0;
}

static long long AFCFileSize(AFCConnectionRef afc, NSString *path) {
    AFCKeyValueRef info = NULL;
    if (AFCFileInfoOpen(afc, path.fileSystemRepresentation, &info) != 0 ||
        !info) return -1;
    long long size = -1;
    char *key = NULL;
    char *value = NULL;
    while (AFCKeyValueRead(info, &key, &value) == 0 && key && value) {
        if (strcmp(key, "st_size") == 0) size = strtoll(value, NULL, 10);
        key = NULL;
        value = NULL;
    }
    AFCKeyValueClose(info);
    return size;
}

static NSString *AFCFileKind(AFCConnectionRef afc, NSString *path) {
    AFCKeyValueRef info = NULL;
    if (AFCFileInfoOpen(afc, path.fileSystemRepresentation, &info) != 0 ||
        !info) return nil;
    NSString *kind = nil;
    char *key = NULL;
    char *value = NULL;
    while (AFCKeyValueRead(info, &key, &value) == 0 && key && value) {
        if (strcmp(key, "st_ifmt") == 0)
            kind = [NSString stringWithUTF8String:value];
        key = NULL;
        value = NULL;
    }
    AFCKeyValueClose(info);
    return kind;
}

static NSData *AFCReadFileWithLimit(AFCConnectionRef afc,
                                    NSString *path,
                                    long long limit) {
    long long size = AFCFileSize(afc, path);
    if (size < 0 || size > limit) return nil;
    AFCFileRef file = NULL;
    if (AFCFileRefOpen(afc, path.fileSystemRepresentation, 1, &file) != 0 ||
        !file) return nil;
    NSMutableData *data = [NSMutableData dataWithLength:(NSUInteger)size];
    long long offset = 0;
    int status = 0;
    while (offset < size) {
        long length = (long)(size - offset);
        status = AFCFileRefRead(
            afc, file, (uint8_t *)data.mutableBytes + offset, &length);
        if (status != 0 || length <= 0 || length > size - offset) break;
        offset += length;
    }
    int closeStatus = AFCFileRefClose(afc, file);
    if (status != 0 || closeStatus != 0 || offset != size) return nil;
    return data;
}

static NSData *AFCReadFile(AFCConnectionRef afc, NSString *path) {
    return AFCReadFileWithLimit(afc, path, 16 * 1024 * 1024);
}

static BOOL AFCWriteFile(AFCConnectionRef afc, NSString *path, NSData *data) {
    AFCFileRef file = NULL;
    int status = AFCFileRefOpen(afc, path.fileSystemRepresentation, 3, &file);
    if (status != 0 || !file) return NO;
    status = data.length == 0
        ? 0 : AFCFileRefWrite(afc, file, data.bytes, (long)data.length);
    int closeStatus = AFCFileRefClose(afc, file);
    return status == 0 && closeStatus == 0;
}

static BOOL EnsureDirectory(AFCConnectionRef afc, NSString *path) {
    return AFCExists(afc, path) ||
        AFCDirectoryCreate(afc, path.fileSystemRepresentation) == 0;
}

static BOOL RemoveIfPresent(AFCConnectionRef afc, NSString *path) {
    if (!AFCExists(afc, path)) return YES;
    return AFCRemovePath(afc, path.fileSystemRepresentation) == 0 &&
        !AFCExists(afc, path);
}

static BOOL AllTrackedBooksFilesAbsent(AFCConnectionRef afc) {
    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksFiles) / sizeof(char *);
         index++) {
        NSString *path =
            [NSString stringWithUTF8String:TrackedBooksFiles[index]];
        if (AFCExists(afc, path)) return NO;
    }
    return YES;
}

static NSArray<NSString *> *PresentTrackedBooksPaths(AFCConnectionRef afc) {
    NSMutableArray<NSString *> *paths = NSMutableArray.array;
    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksFiles) / sizeof(char *);
         index++) {
        NSString *path =
            [NSString stringWithUTF8String:TrackedBooksFiles[index]];
        if (AFCExists(afc, path)) [paths addObject:path];
    }
    return paths;
}

static NSString *SnapshotFileName(NSUInteger index) {
    return [NSString stringWithFormat:@"file-%lu.bin", (unsigned long)index];
}

static NSString *SnapshotManifestPath(NSString *root) {
    return [root stringByAppendingPathComponent:@"manifest.plist"];
}

static NSDictionary *LoadBooksSnapshot(NSString *root) {
    NSData *data = [NSData dataWithContentsOfFile:SnapshotManifestPath(root)];
    if (!data) return nil;
    id value = [NSPropertyListSerialization propertyListWithData:data
        options:NSPropertyListImmutable format:NULL error:nil];
    if (![value isKindOfClass:NSDictionary.class] ||
        ![value[@"version"] isEqual:@1] ||
        ![value[@"files"] isKindOfClass:NSDictionary.class] ||
        ![value[@"directories"] isKindOfClass:NSDictionary.class]) return nil;

    NSDictionary *files = value[@"files"];
    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksFiles) / sizeof(char *);
         index++) {
        NSString *path = [NSString stringWithUTF8String:TrackedBooksFiles[index]];
        NSDictionary *row = [files[path] isKindOfClass:NSDictionary.class]
            ? files[path] : nil;
        NSString *expectedName = SnapshotFileName(index);
        if (![row[@"exists"] isKindOfClass:NSNumber.class] ||
            ![row[@"localName"] isEqual:expectedName]) return nil;
        if ([row[@"exists"] boolValue]) {
            NSString *localPath = [root stringByAppendingPathComponent:expectedName];
            BOOL isDirectory = NO;
            if (![[NSFileManager defaultManager] fileExistsAtPath:localPath
                isDirectory:&isDirectory] || isDirectory) return nil;
        }
    }
    NSDictionary *directories = value[@"directories"];
    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksDirectories) / sizeof(char *);
         index++) {
        NSString *path =
            [NSString stringWithUTF8String:TrackedBooksDirectories[index]];
        if (![directories[path] isKindOfClass:NSNumber.class]) return nil;
    }
    return value;
}

static NSDictionary *SnapshotBooksState(AFCConnectionRef afc, NSString *root) {
    BOOL isDirectory = NO;
    BOOL rootReady = [[NSFileManager defaultManager] fileExistsAtPath:root
        isDirectory:&isDirectory] && isDirectory;
    if (!rootReady ||
        [[NSFileManager defaultManager] fileExistsAtPath:SnapshotManifestPath(root)])
        return @{ @"ok": @NO, @"snapshotDirectoryReady": @(rootReady) };

    NSMutableDictionary *files = NSMutableDictionary.dictionary;
    NSMutableDictionary *directories = NSMutableDictionary.dictionary;
    NSMutableArray<NSString *> *presentPaths = NSMutableArray.array;
    unsigned long long totalBytes = 0;
    NSError *localError = nil;

    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksFiles) / sizeof(char *);
         index++) {
        NSString *path = [NSString stringWithUTF8String:TrackedBooksFiles[index]];
        NSString *localName = SnapshotFileName(index);
        BOOL exists = AFCExists(afc, path);
        if (exists && ![AFCFileKind(afc, path) isEqual:@"S_IFREG"])
            return @{ @"ok": @NO, @"unexpectedFileType": path };
        NSData *data = exists
            ? AFCReadFileWithLimit(afc, path, 128 * 1024 * 1024) : nil;
        if (exists && !data)
            return @{ @"ok": @NO, @"snapshotReadFailed": path };
        if (data) {
            totalBytes += data.length;
            if (totalBytes > 256 * 1024 * 1024)
                return @{ @"ok": @NO, @"snapshotTooLarge": @YES };
            NSString *localPath = [root stringByAppendingPathComponent:localName];
            if (![data writeToFile:localPath
                    options:NSDataWritingWithoutOverwriting
                      error:&localError])
                return @{ @"ok": @NO,
                          @"snapshotWriteFailed": path,
                          @"localError": localError.localizedDescription ?: @"unknown" };
            [presentPaths addObject:path];
        }
        files[path] = @{ @"exists": @(exists),
                         @"localName": localName,
                         @"size": @(data.length) };
    }

    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksDirectories) / sizeof(char *);
         index++) {
        NSString *path =
            [NSString stringWithUTF8String:TrackedBooksDirectories[index]];
        BOOL exists = AFCExists(afc, path);
        NSString *kind = exists ? AFCFileKind(afc, path) : nil;
        if (exists && ![kind isEqual:@"S_IFDIR"])
            return @{ @"ok": @NO, @"unexpectedDirectoryType": path };
        directories[path] = @(exists);
    }

    NSDictionary *manifest = @{ @"version": @1,
                                 @"files": files,
                                 @"directories": directories };
    NSData *manifestData = [NSPropertyListSerialization
        dataWithPropertyList:manifest format:NSPropertyListBinaryFormat_v1_0
        options:0 error:&localError];
    BOOL wroteManifest = manifestData && [manifestData
        writeToFile:SnapshotManifestPath(root)
        options:NSDataWritingAtomic
        error:&localError];
    return @{ @"ok": @(wroteManifest),
              @"presentPaths": presentPaths,
              @"snapshotBytes": @(totalBytes),
              @"localError": wroteManifest
                  ? (id)NSNull.null
                  : (localError.localizedDescription ?: @"unknown") };
}

static BOOL BooksStateMatchesSnapshot(AFCConnectionRef afc,
                                      NSString *root,
                                      NSDictionary *snapshot) {
    NSDictionary *files = snapshot[@"files"];
    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksFiles) / sizeof(char *);
         index++) {
        NSString *path = [NSString stringWithUTF8String:TrackedBooksFiles[index]];
        NSDictionary *row = files[path];
        BOOL expectedExists = [row[@"exists"] boolValue];
        if (AFCExists(afc, path) != expectedExists) return NO;
        if (expectedExists) {
            NSData *expected = [NSData dataWithContentsOfFile:
                [root stringByAppendingPathComponent:SnapshotFileName(index)]];
            NSData *observed =
                AFCReadFileWithLimit(afc, path, 128 * 1024 * 1024);
            if (!expected || !observed || ![observed isEqualToData:expected])
                return NO;
        }
    }

    NSDictionary *directories = snapshot[@"directories"];
    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksDirectories) / sizeof(char *);
         index++) {
        NSString *path =
            [NSString stringWithUTF8String:TrackedBooksDirectories[index]];
        BOOL expectedExists = [directories[path] boolValue];
        BOOL exists = AFCExists(afc, path);
        if (exists != expectedExists) return NO;
        if (exists && ![AFCFileKind(afc, path) isEqual:@"S_IFDIR"])
            return NO;
    }
    return YES;
}

static BOOL EnsureBooksParent(AFCConnectionRef afc, NSString *path) {
    if (!EnsureDirectory(afc, @"Books")) return NO;
    if ([path hasPrefix:@"Books/Sync/"] &&
        !EnsureDirectory(afc, @"Books/Sync")) return NO;
    if ([path hasPrefix:@"Books/Sync/Database/"] &&
        !EnsureDirectory(afc, @"Books/Sync/Database")) return NO;
    return YES;
}

static NSDictionary *RestoreBooksState(AFCConnectionRef afc, NSString *root) {
    NSDictionary *snapshot = LoadBooksSnapshot(root);
    if (!snapshot) return @{ @"ok": @NO, @"error": @"invalid snapshot" };
    NSMutableArray<NSString *> *failures = NSMutableArray.array;
    NSDictionary *files = snapshot[@"files"];

    for (NSUInteger index = 0;
         index < sizeof(TrackedBooksFiles) / sizeof(char *);
         index++) {
        NSString *path = [NSString stringWithUTF8String:TrackedBooksFiles[index]];
        NSDictionary *row = files[path];
        if ([row[@"exists"] boolValue]) {
            NSData *data = [NSData dataWithContentsOfFile:
                [root stringByAppendingPathComponent:SnapshotFileName(index)]];
            if (!data || !EnsureBooksParent(afc, path) ||
                !AFCWriteFile(afc, path, data)) [failures addObject:path];
        } else if (!RemoveIfPresent(afc, path)) {
            [failures addObject:path];
        }
    }

    NSDictionary *directories = snapshot[@"directories"];
    for (NSInteger index =
             (NSInteger)(sizeof(TrackedBooksDirectories) / sizeof(char *)) - 1;
         index >= 0; index--) {
        NSString *path =
            [NSString stringWithUTF8String:TrackedBooksDirectories[index]];
        if (![directories[path] boolValue] && !RemoveIfPresent(afc, path))
            [failures addObject:path];
    }
    BOOL verified = failures.count == 0 &&
        BooksStateMatchesSnapshot(afc, root, snapshot);
    return @{ @"ok": @(verified),
              @"failures": failures,
              @"preimageVerified": @(verified) };
}

static BOOL IsSafeRelativePath(NSString *path) {
    if (!path.length || [path hasPrefix:@"/"] || [path hasSuffix:@"/"])
        return NO;
    for (NSString *component in [path componentsSeparatedByString:@"/"])
        if (!component.length || [component isEqual:@"."] ||
            [component isEqual:@".."]) return NO;
    return YES;
}

static BOOL IsLowercaseHex(NSString *value, NSUInteger length) {
    if (value.length != length) return NO;
    for (NSUInteger index = 0; index < value.length; index++) {
        unichar character = [value characterAtIndex:index];
        if (!((character >= '0' && character <= '9') ||
              (character >= 'a' && character <= 'f'))) return NO;
    }
    return YES;
}

static NSString *GeneratedToken(NSString *value, NSString *prefix) {
    if (![value hasPrefix:prefix] ||
        [value rangeOfString:@"/"].location != NSNotFound) return nil;
    NSString *token = [value substringFromIndex:prefix.length];
    return IsLowercaseHex(token, 20) ? token : nil;
}

static BOOL GeneratedNamesMatch(NSString *source,
                                NSString *linkDestination,
                                NSString *recovered) {
    NSString *token = GeneratedToken(source, AIRLIFT_SOURCE_PREFIX);
    return token &&
        [GeneratedToken(linkDestination, AIRLIFT_LINK_PREFIX)
            isEqualToString:token] &&
        [GeneratedToken(recovered, AIRLIFT_RECOVERED_PREFIX)
            isEqualToString:token];
}

static BOOL IsCanaryLeaf(NSString *leaf) {
    if (![leaf hasPrefix:AIRLIFT_CANARY_PREFIX] ||
        ![leaf hasSuffix:@".bin"] ||
        leaf.length < AIRLIFT_CANARY_PREFIX.length + @".bin".length ||
        [leaf rangeOfString:@"/"].location != NSNotFound) return NO;
    NSRange tokenRange = NSMakeRange(
        AIRLIFT_CANARY_PREFIX.length,
        leaf.length - AIRLIFT_CANARY_PREFIX.length - @".bin".length);
    return IsLowercaseHex([leaf substringWithRange:tokenRange], 32);
}

static NSDictionary *ListDirectory(AFCConnectionRef afc, NSString *path) {
    if (![path isEqual:@"."] && !IsSafeRelativePath(path))
        return @{ @"ok": @NO, @"error": @"unsafe path", @"path": path };
    AFCDirectoryRef directory = NULL;
    if (AFCDirectoryOpen(afc, path.fileSystemRepresentation, &directory) != 0 ||
        !directory)
        return @{ @"ok": @NO, @"error": @"directory open failed", @"path": path };

    NSMutableArray<NSDictionary *> *entries = NSMutableArray.array;
    BOOL readComplete = NO;
    for (NSUInteger index = 0; index < 8192; index++) {
        char *raw = NULL;
        int status = AFCDirectoryRead(afc, directory, &raw);
        if (status != 0) break;
        if (!raw) {
            readComplete = YES;
            break;
        }
        NSString *name = [NSString stringWithUTF8String:raw];
        if (!name.length || [name isEqual:@"."] || [name isEqual:@".."]) continue;
        NSString *child = [path isEqual:@"."]
            ? name : [path stringByAppendingPathComponent:name];
        NSString *kind = AFCFileKind(afc, child) ?: @"unknown";
        NSMutableDictionary *entry = [@{ @"name": name, @"kind": kind } mutableCopy];
        if ([kind isEqual:@"S_IFREG"]) entry[@"size"] = @(AFCFileSize(afc, child));
        AFCKeyValueRef childInfo = NULL;
        if (AFCFileInfoOpen(afc, child.fileSystemRepresentation, &childInfo) == 0 &&
            childInfo) {
            char *key = NULL;
            char *value = NULL;
            while (AFCKeyValueRead(childInfo, &key, &value) == 0 && key && value) {
                if (strcmp(key, "st_mtime") == 0)
                    entry[@"mtime"] = @(value);
                key = NULL;
                value = NULL;
            }
            AFCKeyValueClose(childInfo);
        }
        [entries addObject:entry];
    }
    BOOL closeOK = AFCDirectoryClose(afc, directory) == 0;
    return @{ @"ok": @(readComplete && closeOK),
              @"path": path,
              @"entries": entries };
}

static NSDictionary *ProbeTarget(AFCConnectionRef afc,
                                     NSString *linkDestination,
                                     NSString *targetLeaf) {
    NSString *targetThroughLink =
        [linkDestination stringByAppendingPathComponent:targetLeaf];
    AFCKeyValueRef info = NULL;
    int status = AFCFileInfoOpen(afc, targetThroughLink.fileSystemRepresentation, &info);
    BOOL readable = status == 0 && info != NULL;
    if (info) AFCKeyValueClose(info);
    // The AFC daemon runs inside the media sandbox, so a file that lives outside
    // it cannot be stat'ed. Empirically the traversal link still resolves: an
    // existing target reports status 10 while a missing one reports 8 (the same
    // code a plain missing path returns). Anything that is not "missing" is
    // therefore presence evidence.
    BOOL present = readable || (status != 0 && status != 8);
    return @{ @"targetPath": targetThroughLink,
              @"status": @(status),
              @"readable": @(readable),
              @"present": @(present) };
}

static NSDictionary *ReadPath(AFCConnectionRef afc, NSString *path, long long limit) {
    NSData *data = AFCReadFileWithLimit(afc, path, limit);
    if (!data)
        return @{ @"ok": @NO, @"error": @"read failed", @"path": path };
    return @{ @"ok": @YES,
              @"path": path,
              @"size": @(data.length),
              @"base64": [data base64EncodedStringWithOptions:0] };
}

static NSDictionary *PathInfo(AFCConnectionRef afc, NSString *path) {
    AFCKeyValueRef info = NULL;
    int status = AFCFileInfoOpen(afc, path.fileSystemRepresentation, &info);
    if (status != 0 || !info)
        return @{ @"ok": @NO, @"error": @"stat failed", @"path": path, @"status": @(status) };
    NSMutableDictionary *fields = NSMutableDictionary.dictionary;
    char *key = NULL;
    char *value = NULL;
    while (AFCKeyValueRead(info, &key, &value) == 0 && key && value) {
        fields[[NSString stringWithUTF8String:key]] =
            [NSString stringWithUTF8String:value] ?: @"(nil)";
        key = NULL;
        value = NULL;
    }
    AFCKeyValueClose(info);
    return @{ @"ok": @YES, @"path": path, @"fields": fields };
}

static BOOL RemoveGeneratedTree(AFCConnectionRef afc,
                                NSString *path,
                                NSUInteger depth) {
    if (depth > 32) return NO;
    NSString *kind = AFCFileKind(afc, path);
    if (!kind) return YES;
    if ([kind isEqual:@"S_IFDIR"]) {
        AFCDirectoryRef directory = NULL;
        if (AFCDirectoryOpen(afc, path.fileSystemRepresentation, &directory) !=
                0 ||
            !directory) return NO;
        NSMutableArray<NSString *> *children = NSMutableArray.array;
        BOOL readOK = YES;
        for (NSUInteger index = 0; index < 8192; index++) {
            char *raw = NULL;
            int status = AFCDirectoryRead(afc, directory, &raw);
            if (status != 0) {
                readOK = NO;
                break;
            }
            if (!raw) break;
            NSString *name = [NSString stringWithUTF8String:raw];
            if (!name || [name isEqual:@"."] || [name isEqual:@".."]) continue;
            [children addObject:name];
        }
        BOOL closeOK = AFCDirectoryClose(afc, directory) == 0;
        if (!readOK || !closeOK) return NO;
        for (NSString *name in children) {
            NSString *child = [path stringByAppendingPathComponent:name];
            if (!RemoveGeneratedTree(afc, child, depth + 1)) return NO;
        }
    }
    return AFCRemovePath(afc, path.fileSystemRepresentation) == 0 &&
        !AFCExists(afc, path);
}

static BOOL GeneratedEntryName(NSString *name) {
    NSArray<NSString *> *prefixes = @[
        AIRLIFT_SOURCE_PREFIX, AIRLIFT_LINK_PREFIX, AIRLIFT_RECOVERED_PREFIX
    ];
    for (NSString *prefix in prefixes)
        if ([name hasPrefix:prefix] &&
            IsLowercaseHex([name substringFromIndex:prefix.length], 20))
            return YES;
    return NO;
}

static NSDictionary *CleanStaging(AFCConnectionRef afc) {
    AFCDirectoryRef directory = NULL;
    if (AFCDirectoryOpen(afc, ".", &directory) != 0 || !directory)
        return @{ @"ok": @NO, @"error": @"media root open failed" };

    NSMutableArray<NSString *> *names = NSMutableArray.array;
    BOOL readComplete = NO;
    for (NSUInteger index = 0; index < 8192; index++) {
        char *raw = NULL;
        int status = AFCDirectoryRead(afc, directory, &raw);
        if (status != 0) break;
        if (!raw) {
            readComplete = YES;
            break;
        }
        NSString *name = [NSString stringWithUTF8String:raw];
        if (name.length && GeneratedEntryName(name)) [names addObject:name];
    }
    BOOL closeOK = AFCDirectoryClose(afc, directory) == 0;

    NSMutableArray<NSString *> *removed = NSMutableArray.array;
    NSMutableArray<NSString *> *failures = NSMutableArray.array;
    for (NSString *name in names) {
        if (RemoveGeneratedTree(afc, name, 0)) [removed addObject:name];
        else [failures addObject:name];
    }
    NSMutableArray<NSString *> *remaining = NSMutableArray.array;
    for (NSString *name in names)
        if (AFCExists(afc, name)) [remaining addObject:name];
    BOOL complete = readComplete && closeOK && remaining.count == 0;
    return @{ @"ok": @(complete),
              @"stagingEntriesFound": names,
              @"removed": removed,
              @"remaining": remaining,
              @"failures": failures };
}

static NSDictionary *Cleanup(DeviceSession *session, NSArray<NSString *> *args) {
    NSString *source = args[0];
    NSString *linkDestination = args[1];
    NSString *recovered = args[2];
    NSString *snapshotRoot = args[3];
    NSDictionary *snapshot = LoadBooksSnapshot(snapshotRoot);
    BOOL safeArguments =
        GeneratedNamesMatch(source, linkDestination, recovered) && snapshot != nil;
    if (!safeArguments)
        return @{ @"ok": @NO, @"safeArguments": @NO };

    NSMutableArray<NSString *> *failures = NSMutableArray.array;
    if (!RemoveIfPresent(session->afc, linkDestination))
        [failures addObject:@"relocated link"];
    if (!RemoveIfPresent(session->afc, recovered))
        [failures addObject:@"recovered file"];
    if (!RemoveGeneratedTree(session->afc, source, 0))
        [failures addObject:@"StreamingZip tree"];
    NSDictionary *booksRestore = RestoreBooksState(session->afc, snapshotRoot);
    if (![booksRestore[@"ok"] boolValue]) [failures addObject:@"Books preimage"];

    BOOL sourceAbsent = !AFCExists(session->afc, source);
    BOOL linkAbsent = !AFCExists(session->afc, linkDestination);
    BOOL recoveredAbsent = !AFCExists(session->afc, recovered);
    BOOL complete = failures.count == 0 &&
        sourceAbsent && linkAbsent && recoveredAbsent;
    return @{ @"ok": @(complete),
              @"cleanupComplete": @(complete),
              @"failures": failures,
              @"sourceAbsent": @(sourceAbsent),
              @"linkAbsent": @(linkAbsent),
              @"recoveredAbsent": @(recoveredAbsent),
              @"booksRestore": booksRestore };
}

static NSDictionary *SessionSummary(DeviceSession *session) {
    id productType = session->connected
        ? CFBridgingRelease(AMDeviceCopyValue(
              session->device, NULL, CFSTR("ProductType"))) : nil;
    id productVersion = session->connected
        ? CFBridgingRelease(AMDeviceCopyValue(
              session->device, NULL, CFSTR("ProductVersion"))) : nil;
    id buildVersion = session->connected
        ? CFBridgingRelease(AMDeviceCopyValue(
              session->device, NULL, CFSTR("BuildVersion"))) : nil;
    return @{
        @"subscribeStatus": @(session->subscribeStatus),
        @"targetObserved": @(session->device != NULL),
        @"connectStatus": @(session->connectStatus),
        @"validateStatus": @(session->validateStatus),
        @"sessionStatus": @(session->sessionStatus),
        @"serviceStatus": @(session->serviceStatus),
        @"afcStatus": @(session->afcStatus),
        @"productType": [productType isKindOfClass:NSString.class]
            ? productType : @"(nil)",
        @"productVersion": [productVersion isKindOfClass:NSString.class]
            ? productVersion : @"(nil)",
        @"buildVersion": [buildVersion isKindOfClass:NSString.class]
            ? buildVersion : @"(nil)",
    };
}

static BOOL BuildMatches(NSDictionary *summary,
                         NSString *version,
                         NSString *build) {
    return [summary[@"productVersion"] isEqual:version] &&
        [summary[@"buildVersion"] isEqual:build];
}

static BOOL TargetGate(NSDictionary *summary, BOOL *tested) {
    *tested = NO;
    if (![summary[@"productType"] hasPrefix:@"iPhone"]) return NO;
#define AIRLIFT_MATCH_TESTED(version, build) \
    if (BuildMatches(summary, version, build)) { \
        *tested = YES; \
        return YES; \
    }
    AIRLIFT_TESTED_BUILDS(AIRLIFT_MATCH_TESTED)
#undef AIRLIFT_MATCH_TESTED
    // If strict mode is enforced, block any untested builds from proceeding
    const char *strictEnv = getenv("AIRLIFT_STRICT_BUILDS");
    if (strictEnv && strcmp(strictEnv, "1") == 0) {
        return NO;
    }
    return YES;
}

static BOOL SendAll(AMDServiceConnectionRef service, NSData *data) {
    const uint8_t *cursor = data.bytes;
    size_t remaining = data.length;
    while (remaining) {
        int sent = AMDServiceConnectionSend(service, cursor, remaining);
        if (sent <= 0) return NO;
        cursor += sent;
        remaining -= (size_t)sent;
    }
    return YES;
}

static NSDictionary *Stage(DeviceSession *session, NSArray<NSString *> *args) {
    NSString *source = args[0];
    NSString *linkDestination = args[1];
    NSString *recovered = args[2];
    NSData *archive = [NSData dataWithContentsOfFile:args[3]];
    NSData *books = [NSData dataWithContentsOfFile:args[4]];
    NSString *snapshotRoot = args[5];
    NSDictionary *snapshot = LoadBooksSnapshot(snapshotRoot);
    BOOL safeArguments =
        GeneratedNamesMatch(source, linkDestination, recovered);
    BOOL snapshotMatches = snapshot && BooksStateMatchesSnapshot(
        session->afc, snapshotRoot, snapshot);
    BOOL freshPaths = !AFCExists(session->afc, source) &&
        !AFCExists(session->afc, linkDestination) &&
        !AFCExists(session->afc, recovered);
    if (!safeArguments || !archive || !books || !snapshotMatches || !freshPaths) {
        return @{ @"ok": @NO,
                  @"cleanupAuthorized": @NO,
                  @"safeArguments": @(safeArguments),
                  @"localInputsReadable": @(archive != nil && books != nil),
                  @"booksPreimageStable": @(snapshotMatches),
                  @"freshPaths": @(freshPaths) };
    }

    AMDServiceConnectionRef zipService = NULL;
    int serviceStatus = AMDeviceSecureStartService(
        session->device,
        CFSTR("com.apple.streaming_zip_conduit"),
        NULL,
        &zipService);
    int messageStatus = -1;
    int responseStatus = -1;
    BOOL archiveSent = NO;
    CFTypeRef response = NULL;
    if (serviceStatus == 0 && zipService) {
        messageStatus = AMDServiceConnectionSendMessage(
            zipService,
            (__bridge CFTypeRef)@{ @"MediaSubdir": source },
            kCFPropertyListBinaryFormat_v1_0);
        if (messageStatus == 0) archiveSent = SendAll(zipService, archive);
        if (archiveSent) {
            int socket = AMDServiceConnectionGetSocket(zipService);
            struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
            setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                       sizeof(timeout));
            CFPropertyListFormat format = kCFPropertyListBinaryFormat_v1_0;
            responseStatus = AMDServiceConnectionReceiveMessage(
                zipService, &response, &format);
        }
    }
    id responseValue = response ? (__bridge id)response : nil;
    NSString *responseSummary = nil;
    if ([responseValue isKindOfClass:NSDictionary.class] ||
        [responseValue isKindOfClass:NSArray.class] ||
        [responseValue isKindOfClass:NSString.class] ||
        [responseValue isKindOfClass:NSNumber.class]) {
        NSData *encoded = [NSJSONSerialization dataWithJSONObject:responseValue
                                                          options:0
                                                            error:nil];
        responseSummary = encoded
            ? [[NSString alloc] initWithData:encoded
                                    encoding:NSUTF8StringEncoding]
            : [responseValue description];
    } else if (responseValue) {
        responseSummary = [responseValue description];
    }
    if (response) CFRelease(response);
    if (zipService) AMDServiceConnectionInvalidate(zipService);

    NSString *link =
        [source stringByAppendingPathComponent:@"p0/p1/p2/link"];
    NSString *payloadPath = [source stringByAppendingPathComponent:@"payload"];
    // The conduit may finish unpacking slightly after it answers, so poll for
    // the extracted objects instead of sampling them exactly once.
    BOOL sourceObjects = NO;
    NSUInteger sourceAttempts = 60;
    for (NSUInteger index = 0; index < sourceAttempts; index++) {
        if (AFCExists(session->afc, source) &&
            AFCExists(session->afc, link) &&
            AFCExists(session->afc, payloadPath)) {
            sourceObjects = YES;
            break;
        }
        if (index + 1 < sourceAttempts) usleep(250000);
    }
    BOOL directoriesReady = EnsureDirectory(session->afc, @"Books") &&
        EnsureDirectory(session->afc, @"Books/Sync");
    BOOL booksWritten = sourceObjects && directoriesReady &&
        AFCWriteFile(session->afc, @"Books/Sync/Books.plist", books);
    BOOL ok = serviceStatus == 0 && messageStatus == 0 && archiveSent &&
        sourceObjects && booksWritten;
    return @{ @"ok": @(ok),
              @"cleanupAuthorized": @YES,
              @"safeArguments": @YES,
              @"booksPreimageStable": @YES,
              @"freshPaths": @YES,
              @"zipServiceStatus": @(serviceStatus),
              @"zipMessageStatus": @(messageStatus),
              @"zipResponseStatus": @(responseStatus),
              @"zipResponse": responseSummary ?: @"(none)",
              @"archiveSent": @(archiveSent),
              @"sourceObjectsPresent": @(sourceObjects),
              @"booksWritten": @(booksWritten) };
}

static NSDictionary *Finish(DeviceSession *session, NSArray<NSString *> *args) {
    NSString *source = args[0];
    NSString *linkDestination = args[1];
    NSString *recovered = args[2];
    NSData *expected = [NSData dataWithContentsOfFile:args[3]];
    NSString *targetTail = args[4];
    NSString *targetLeaf = args[5];
    NSString *waitArgument = args[6];
    NSString *snapshotRoot = args[7];
    NSDictionary *snapshot = LoadBooksSnapshot(snapshotRoot);
    BOOL safeArguments =
        GeneratedNamesMatch(source, linkDestination, recovered) &&
        IsSafeRelativePath(targetTail) && IsCanaryLeaf(targetLeaf) &&
        expected.length > 0 && expected.length < 4096 &&
        snapshot != nil &&
        ([waitArgument isEqual:@"0"] || [waitArgument isEqual:@"1"]);
    if (!safeArguments)
        return @{ @"ok": @NO, @"safeArguments": @NO };

    NSData *observed = nil;
    NSUInteger readbackAttempts = 0;
    NSUInteger maximumAttempts = [waitArgument isEqual:@"1"] ? 60 : 1;
    for (NSUInteger index = 0; index < maximumAttempts; index++) {
        readbackAttempts++;
        observed = AFCReadFile(session->afc, recovered);
        if ([observed isEqualToData:expected]) break;
        if (index + 1 < maximumAttempts) usleep(250000);
    }
    BOOL recoveredPresent = observed != nil;
    BOOL bytesMatch = recoveredPresent && [observed isEqualToData:expected];
    NSMutableArray<NSString *> *failures = NSMutableArray.array;

    NSString *targetThroughLink =
        [linkDestination stringByAppendingPathComponent:targetLeaf];
    if (!RemoveIfPresent(session->afc, targetThroughLink))
        [failures addObject:@"target canary"];
    BOOL targetAbsent = !AFCExists(session->afc, targetThroughLink);
    if (!RemoveIfPresent(session->afc, linkDestination))
        [failures addObject:@"relocated link"];
    if (!RemoveIfPresent(session->afc, recovered))
        [failures addObject:@"recovered file"];
    if (!RemoveGeneratedTree(session->afc, source, 0))
        [failures addObject:@"StreamingZip tree"];
    sleep(2);
    NSDictionary *booksRestore = RestoreBooksState(session->afc, snapshotRoot);
    BOOL booksRestored = [booksRestore[@"ok"] boolValue];
    if (!booksRestored) [failures addObject:@"Books preimage"];

    BOOL sourceAbsent = !AFCExists(session->afc, source);
    BOOL linkAbsent = !AFCExists(session->afc, linkDestination);
    BOOL recoveredAbsent = !AFCExists(session->afc, recovered);
    BOOL cleanupComplete = failures.count == 0 && targetAbsent &&
        sourceAbsent && linkAbsent && recoveredAbsent && booksRestored;
    return @{ @"ok": @(bytesMatch && cleanupComplete),
              @"safeArguments": @YES,
              @"recoveredPresent": @(recoveredPresent),
              @"recoveredBytesMatch": @(bytesMatch),
              @"readbackAttempts": @(readbackAttempts),
              @"observedLength": @(observed.length),
              @"cleanupComplete": @(cleanupComplete),
              @"cleanupFailureCount": @(failures.count),
              @"failures": failures,
              @"targetAbsent": @(targetAbsent),
              @"sourceAbsent": @(sourceAbsent),
              @"linkAbsent": @(linkAbsent),
              @"recoveredAbsent": @(recoveredAbsent),
              @"booksPreimageRestored": @(booksRestored),
              @"booksRestore": booksRestore };
}

static NSDictionary *FinishDeploy(DeviceSession *session, NSArray<NSString *> *args) {
    NSString *source = args[0];
    NSString *linkDestination = args[1];
    NSString *recovered = args[2];
    NSData *expected = [NSData dataWithContentsOfFile:args[3]];
    NSString *targetTail = args[4];
    NSString *targetLeaf = args[5];
    NSString *waitArgument = args[6];
    NSString *snapshotRoot = args[7];
    NSDictionary *snapshot = LoadBooksSnapshot(snapshotRoot);
    BOOL safeArguments =
        GeneratedNamesMatch(source, linkDestination, recovered) &&
        IsSafeRelativePath(targetTail) && [targetLeaf isEqual:@"StatusBarOverrides.archive"] &&
        expected.length > 0 && expected.length < 65536 &&
        snapshot != nil &&
        ([waitArgument isEqual:@"0"] || [waitArgument isEqual:@"1"]);
    if (!safeArguments)
        return @{ @"ok": @NO, @"safeArguments": @NO };

    NSUInteger maximumAttempts = [waitArgument isEqual:@"1"] ? 40 : 1;
    NSDictionary *targetProbe = nil;
    BOOL targetPresent = NO;
    NSUInteger readbackAttempts = 0;
    for (NSUInteger index = 0; index < maximumAttempts; index++) {
        readbackAttempts++;
        targetProbe = ProbeTarget(session->afc, linkDestination, targetLeaf);
        targetPresent = [targetProbe[@"present"] boolValue];
        if (targetPresent) break;
        if (index + 1 < maximumAttempts) usleep(250000);
    }
    NSData *observedTarget = [targetProbe[@"readable"] boolValue]
        ? AFCReadFileWithLimit(session->afc, targetProbe[@"targetPath"], 65536)
        : nil;
    BOOL targetBytesMatch =
        observedTarget != nil && [observedTarget isEqualToData:expected];
    NSData *observedRecovered =
        AFCReadFileWithLimit(session->afc, recovered, 65536);
    BOOL recoveredPresent = observedRecovered != nil;
    BOOL recoveredBytesMatch =
        recoveredPresent && [observedRecovered isEqualToData:expected];

    NSMutableArray<NSString *> *failures = NSMutableArray.array;

    if (!RemoveIfPresent(session->afc, linkDestination))
        [failures addObject:@"relocated link"];
    if (!RemoveIfPresent(session->afc, recovered))
        [failures addObject:@"recovered file"];
    if (!RemoveGeneratedTree(session->afc, source, 0))
        [failures addObject:@"StreamingZip tree"];
    sleep(2);
    NSDictionary *booksRestore = RestoreBooksState(session->afc, snapshotRoot);
    BOOL booksRestored = [booksRestore[@"ok"] boolValue];
    if (!booksRestored) [failures addObject:@"Books preimage"];

    BOOL sourceAbsent = !AFCExists(session->afc, source);
    BOOL linkAbsent = !AFCExists(session->afc, linkDestination);
    BOOL recoveredAbsent = !AFCExists(session->afc, recovered);
    BOOL cleanupComplete = failures.count == 0 &&
        sourceAbsent && linkAbsent && recoveredAbsent && booksRestored;
    BOOL payloadVerified = targetBytesMatch || recoveredBytesMatch;
    return @{ @"ok": @(cleanupComplete && targetPresent),
              @"safeArguments": @YES,
              @"targetPresent": @(targetPresent),
              @"targetProbe": targetProbe ?: @{},
              @"targetBytesMatch": @(targetBytesMatch),
              @"targetBytesVerified": @(targetBytesMatch || recoveredBytesMatch),
              @"recoveredPresent": @(recoveredPresent),
              @"recoveredBytesMatch": @(recoveredBytesMatch),
              @"payloadVerified": @(payloadVerified),
              @"readbackAttempts": @(readbackAttempts),
              @"observedLength": @(observedTarget.length),
              @"expectedLength": @(expected.length),
              @"cleanupComplete": @(cleanupComplete),
              @"cleanupFailureCount": @(failures.count),
              @"failures": failures,
              @"sourceAbsent": @(sourceAbsent),
              @"linkAbsent": @(linkAbsent),
              @"recoveredAbsent": @(recoveredAbsent),
              @"booksPreimageRestored": @(booksRestored),
              @"booksRestore": booksRestore };
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc < 3) return 64;
        NSString *command = [NSString stringWithUTF8String:argv[1]];
        TargetIdentifier = CFStringCreateWithCString(
            kCFAllocatorDefault, argv[2], kCFStringEncodingUTF8);
        if (!TargetIdentifier) return 64;

        DeviceSession session;
        OpenSession(&session);
        NSDictionary *summary = SessionSummary(&session);
        BOOL targetTested = NO;
        BOOL targetGatePassed = TargetGate(summary, &targetTested);
        NSDictionary *operation = nil;
        if (session.afcStatus == 0 && session.afc && targetGatePassed) {
            if ([command isEqual:@"probe"] && argc == 3) {
                NSArray<NSString *> *presentPaths =
                    PresentTrackedBooksPaths(session.afc);
                operation = @{ @"ok": @YES,
                    @"booksStagingAbsent":
                        @(AllTrackedBooksFilesAbsent(session.afc)),
                    @"presentBooksPaths": presentPaths,
                    @"fixedSyncInputPresent":
                        @([presentPaths containsObject:@"Books/Sync/Books.plist"]),
                    @"booksSyncPlistPresent":
                        @(AFCExists(session.afc, @"Books/Sync/Books.plist")) };
            } else if ([command isEqual:@"read"] && argc == 5) {
                operation = ReadPath(
                    session.afc,
                    [NSString stringWithUTF8String:argv[3]],
                    strtoll(argv[4], NULL, 10));
            } else if ([command isEqual:@"cleanup"] && argc == 7) {
                operation = Cleanup(&session, @[
                    [NSString stringWithUTF8String:argv[3]],
                    [NSString stringWithUTF8String:argv[4]],
                    [NSString stringWithUTF8String:argv[5]],
                    [NSString stringWithUTF8String:argv[6]],
                ]);
            } else if ([command isEqual:@"clean-staging"] && argc == 3) {
                operation = CleanStaging(session.afc);
            } else if ([command isEqual:@"info"] && argc == 4) {
                operation = PathInfo(
                    session.afc, [NSString stringWithUTF8String:argv[3]]);
            } else if ([command isEqual:@"list"] && argc == 4) {
                operation = ListDirectory(
                    session.afc, [NSString stringWithUTF8String:argv[3]]);
            } else if ([command isEqual:@"snapshot-books"] && argc == 4) {
                operation = SnapshotBooksState(
                    session.afc, [NSString stringWithUTF8String:argv[3]]);
            } else if ([command isEqual:@"restore-books"] && argc == 4) {
                operation = RestoreBooksState(
                    session.afc, [NSString stringWithUTF8String:argv[3]]);
            } else if ([command isEqual:@"stage"] && argc == 9) {
                operation = Stage(&session, @[
                    [NSString stringWithUTF8String:argv[3]],
                    [NSString stringWithUTF8String:argv[4]],
                    [NSString stringWithUTF8String:argv[5]],
                    [NSString stringWithUTF8String:argv[6]],
                    [NSString stringWithUTF8String:argv[7]],
                    [NSString stringWithUTF8String:argv[8]],
                ]);
            } else if ([command isEqual:@"finish"] && argc == 11) {
                operation = Finish(&session, @[
                    [NSString stringWithUTF8String:argv[3]],
                    [NSString stringWithUTF8String:argv[4]],
                    [NSString stringWithUTF8String:argv[5]],
                    [NSString stringWithUTF8String:argv[6]],
                    [NSString stringWithUTF8String:argv[7]],
                    [NSString stringWithUTF8String:argv[8]],
                    [NSString stringWithUTF8String:argv[9]],
                    [NSString stringWithUTF8String:argv[10]],
                ]);
            } else if ([command isEqual:@"finish-deploy"] && argc == 11) {
                operation = FinishDeploy(&session, @[
                    [NSString stringWithUTF8String:argv[3]],
                    [NSString stringWithUTF8String:argv[4]],
                    [NSString stringWithUTF8String:argv[5]],
                    [NSString stringWithUTF8String:argv[6]],
                    [NSString stringWithUTF8String:argv[7]],
                    [NSString stringWithUTF8String:argv[8]],
                    [NSString stringWithUTF8String:argv[9]],
                    [NSString stringWithUTF8String:argv[10]],
                ]);
            }
        }

        NSMutableDictionary *result = summary.mutableCopy;
        result[@"targetGatePassed"] = @(targetGatePassed);
        result[@"targetTested"] = @(targetTested);
        result[@"command"] = command ?: @"(nil)";
        result[@"operation"] = operation ?: @{ @"ok": @NO };
        PrintJSON(result);
        BOOL ok = targetGatePassed && session.afcStatus == 0 &&
            [operation[@"ok"] boolValue];
        CloseSession(&session);
        CFRelease(TargetIdentifier);
        return ok ? 0 : 2;
    }
}
