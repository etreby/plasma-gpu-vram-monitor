import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15 as QQC
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.components 3.0 as PC
import org.kde.plasma.plasmoid 2.0

Item {
    id: root
    property var cards: []
    property var unavailableDevices: []
    property string selectedGPU: ""
    property string selectedPID: ""
    property string searchText: ""
    property int sortMode: 0
    property bool tasksPaused: false
    property bool sampling: false
    property var taskCache: ({})
    readonly property bool wantsProcesses: plasmoid.expanded
    readonly property var panelCards: cards.filter(function(c) { return !c.processOnly })
    readonly property var selectedCard: {
        for (var i = 0; i < cards.length; ++i) if (cards[i].id === selectedGPU) return cards[i]
        return cards.length ? cards[0] : null
    }
    readonly property var taskInfo: selectedCard && taskCache[selectedCard.id] ? taskCache[selectedCard.id] : {status: "loading", rows: [], note: "Collecting process information…", usageLabel: "GPU activity"}
    readonly property var visibleTasks: {
        var needle = searchText.toLowerCase().trim()
        var rows = taskInfo.rows.filter(function(p) { return !needle || p.name.toLowerCase().indexOf(needle) !== -1 || String(p.pid).indexOf(needle) !== -1 })
        return rows.slice().sort(function(a, b) {
            if (sortMode === 2) return a.name.localeCompare(b.name) || a.pid - b.pid
            var key = sortMode === 1 ? "gpuUsage" : "memoryBytes"
            var av = a[key] === null ? -1 : a[key], bv = b[key] === null ? -1 : b[key]
            return bv - av || a.pid - b.pid
        })
    }
    function requestSample() {
        if (process.connectedSources.length === 0) { sampling = true; process.connectSource(command) }
    }
    function selectGPU(identity) { selectedGPU = identity; selectedPID = ""; searchText = "" }
    function selectedIndex() {
        for (var i = 0; i < cards.length; ++i) if (selectedCard && cards[i].id === selectedCard.id) return i
        return 0
    }
    function processMemory(value) {
        if (value === null || value === undefined) return "—"
        return value >= 1073741824 ? (value / 1073741824).toFixed(2) + " GiB" : (value / 1048576).toFixed(1) + " MiB"
    }
    function processUsage(value) { return value === null || value === undefined ? "—" : value.toFixed(1) + "%" }
    function emptyTasks() {
        if (taskInfo.status === "loading") return tasksPaused ? "Task list paused" : "Loading GPU processes…"
        if (taskInfo.status === "unavailable") return "Process information unavailable"
        if (searchText.length) return "No matching processes"
        return taskInfo.source === "DRM fdinfo" ? "No visible GPU processes" : "No GPU processes reported"
    }
    property bool healthy: false
    property string problem: "Loading GPU sensors…"
    property double lastUpdate: 0
    readonly property string command: "python3 " + shellQuote(decodeURIComponent(Qt.resolvedUrl("../scripts/gpu-panel-data.py").toString().replace(/^file:\/\//, ""))) + (wantsProcesses ? (tasksPaused ? " --task-inventory" : " --processes") : "")
    function shellQuote(value) { return "'" + value.replace(/'/g, "'\\''") + "'" }
    function temp(v) { return v === null || v === undefined ? "—" : Math.round(v) + "°" }
    function percent(v) { return v === null || v === undefined ? "—" : Math.round(v) + "%" }
    function memory(c) { return c.used === null || !c.total ? "—" : (c.used/1024).toFixed(1) + " / " + Math.round(c.total/1024) + " GiB" }
    function heat(v) { return v >= 95 ? PlasmaCore.Theme.negativeTextColor : v >= 80 ? PlasmaCore.Theme.neutralTextColor : PlasmaCore.Theme.textColor }
    function deviceStatus(device) {
        return device.status === "suspended" ? "Suspended" : device.status === "no-driver" ? "No driver bound" : "No readable sensors exposed by driver"
    }
    function details() {
        if (!healthy) return problem
        return cards.map(function(c) { return c.name + "\nCore: " + temp(c.core) + "C · Hotspot: " + temp(c.junction) + "C · VRAM: " + temp(c.vram) + "C\nGPU load: " + percent(c.load) + " · Memory activity: " + percent(c.memoryLoad) + "\nVRAM used: " + memory(c) + "\nThermals: " + (c.thermalSupport || "unavailable") }).join("\n\n") + (unavailableDevices.length ? "\n\n" + unavailableDevices.map(function(d) { return d.name + ": " + deviceStatus(d) }).join("\n") : "") + "\n\nUpdates every 3 seconds. Temperatures: core / VRAM."
    }
    Plasmoid.preferredRepresentation: Plasmoid.compactRepresentation
    Plasmoid.toolTipMainText: "GPU & VRAM Monitor"
    Plasmoid.toolTipSubText: details()
    function shortName(card) {
        var name = card.name.replace(/ (GeForce )?RTX.*$/, "")
        return name === "NVIDIA" || name === "" ? "GPU " + card.index : name
    }
    function ratio(card) { return card.total && card.used !== null ? Math.max(0, Math.min(1, card.used / card.total)) : 0 }
    readonly property color secondary: PlasmaCore.Theme.disabledTextColor
    Plasmoid.compactRepresentation: FocusScope {
        id: compact
        Layout.minimumWidth: units.gridUnit * Math.max(1, root.panelCards.length) * 14
        Layout.preferredWidth: Layout.minimumWidth
        Layout.maximumWidth: Layout.minimumWidth
        Layout.fillHeight: true
        activeFocusOnTab: true
        Accessible.name: "GPU & VRAM Monitor"
        Accessible.description: root.details()
        Keys.onReturnPressed: plasmoid.expanded = !plasmoid.expanded
        Keys.onSpacePressed: plasmoid.expanded = !plasmoid.expanded
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            border.width: compact.activeFocus ? 1 : 0
            border.color: PlasmaCore.Theme.highlightColor
            radius: 3
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: units.smallSpacing * 2
            anchors.rightMargin: units.smallSpacing * 2
            spacing: units.largeSpacing * 2
            Repeater {
                model: root.panelCards
                delegate: ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 1
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: units.smallSpacing
                        PC.Label {
                            text: root.shortName(modelData)
                            font.bold: true
                            font.pixelSize: units.gridUnit * 0.65
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }
                        PC.Label { text: "Core"; color: root.secondary; font.pixelSize: units.gridUnit * 0.56 }
                        PC.Label { text: root.healthy ? root.temp(modelData.core) : "—"; font.bold: true; font.pixelSize: units.gridUnit * 0.7; color: root.healthy ? root.heat(modelData.core) : root.secondary }
                        PC.Label { text: "VRAM"; color: root.secondary; font.pixelSize: units.gridUnit * 0.56; Layout.leftMargin: units.smallSpacing }
                        PC.Label { text: root.healthy ? root.temp(modelData.vram) : "—"; font.bold: true; font.pixelSize: units.gridUnit * 0.7; color: root.healthy ? root.heat(modelData.vram) : root.secondary }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: units.smallSpacing
                        PC.Label { text: root.healthy ? "GPU " + root.percent(modelData.load) : "Offline"; font.pixelSize: units.gridUnit * 0.56; color: root.secondary }
                        Item { Layout.fillWidth: true }
                        PC.Label { text: root.healthy ? root.memory(modelData) : "—"; font.pixelSize: units.gridUnit * 0.56; color: root.secondary }
                        Rectangle {
                            Layout.preferredWidth: units.gridUnit * 2
                            Layout.preferredHeight: 2
                            color: Qt.rgba(PlasmaCore.Theme.textColor.r, PlasmaCore.Theme.textColor.g, PlasmaCore.Theme.textColor.b, 0.15)
                            Rectangle {
                                width: parent.width * root.ratio(modelData)
                                height: parent.height
                                color: root.healthy ? PlasmaCore.Theme.highlightColor : root.secondary
                            }
                            visible: root.healthy && modelData.total > 0
                        }
                    }
                }
            }
            PC.Label { visible: root.panelCards.length === 0; text: root.problem; elide: Text.ElideRight; Layout.fillWidth: true; color: root.secondary }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                compact.forceActiveFocus()
                var index = Math.min(root.panelCards.length - 1, Math.max(0, Math.floor(mouse.x / (width / Math.max(1, root.panelCards.length)))))
                var card = root.panelCards[index]
                if (card && (!plasmoid.expanded || root.selectedGPU !== card.id)) {
                    root.selectGPU(card.id); plasmoid.expanded = true; root.requestSample()
                } else plasmoid.expanded = !plasmoid.expanded
            }
        }
    }
    Plasmoid.fullRepresentation: Item {
        Layout.minimumWidth: units.gridUnit * 36
        Layout.preferredWidth: units.gridUnit * 42
        Layout.minimumHeight: units.gridUnit * 36
        Layout.preferredHeight: units.gridUnit * 42
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: units.largeSpacing
            spacing: units.smallSpacing * 2
            RowLayout {
                Layout.fillWidth: true
                PC.Label { text: "GPU activity"; font.bold: true; font.pointSize: PlasmaCore.Theme.defaultFont.pointSize * 1.3; Layout.fillWidth: true }
                PC.Label { text: !root.healthy ? "Disconnected" : root.tasksPaused ? "Tasks paused" : "Live · 3 s"; color: root.secondary }
                PC.ToolButton {
                    icon.name: root.tasksPaused ? "media-playback-start" : "media-playback-pause"
                    Accessible.name: root.tasksPaused ? "Resume task updates" : "Pause task updates"
                    QQC.ToolTip.text: Accessible.name
                    QQC.ToolTip.visible: hovered
                    onClicked: { root.tasksPaused = !root.tasksPaused; if (!root.tasksPaused) root.requestSample() }
                }
                PC.ToolButton {
                    icon.name: "view-refresh"
                    enabled: !root.tasksPaused && !root.sampling
                    Accessible.name: "Refresh GPU processes"
                    QQC.ToolTip.text: Accessible.name
                    QQC.ToolTip.visible: hovered
                    onClicked: root.requestSample()
                }
            }
            PC.ComboBox {
                Layout.fillWidth: true
                model: root.cards.map(function(c) { return c.name })
                currentIndex: root.selectedIndex()
                enabled: root.cards.length > 0
                Accessible.name: "Select GPU"
                onActivated: root.selectGPU(root.cards[index].id)
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: units.largeSpacing
                PC.Label { text: "GPU  " + (root.selectedCard && root.healthy ? root.percent(root.selectedCard.load) : "—"); font.bold: true; Layout.fillWidth: true }
                PC.Label { text: "Core  " + (root.selectedCard && root.healthy ? root.temp(root.selectedCard.core) : "—") }
                PC.Label { text: "Hotspot  " + (root.selectedCard && root.healthy ? root.temp(root.selectedCard.junction) : "—") }
                PC.Label { text: "VRAM  " + (root.selectedCard && root.healthy ? root.temp(root.selectedCard.vram) : "—") }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: units.smallSpacing
                RowLayout {
                    Layout.fillWidth: true
                    PC.Label { text: root.selectedCard && root.selectedCard.used !== null ? root.memory(root.selectedCard) + " VRAM allocated" : "Device VRAM allocation unavailable"; color: root.secondary; Layout.fillWidth: true }
                    PC.Label { text: root.selectedCard ? "Thermals: " + root.selectedCard.thermalSupport : ""; color: root.selectedCard && root.selectedCard.thermalSupport === "experimental" ? PlasmaCore.Theme.neutralTextColor : root.secondary }
                }
                PC.ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: root.selectedCard && root.healthy ? root.ratio(root.selectedCard) : 0; Accessible.name: "Device VRAM allocation" }
            }
            RowLayout {
                Layout.fillWidth: true
                PC.Label { text: "Processes"; font.bold: true }
                PC.Label { text: root.visibleTasks.length + (root.searchText.length ? " / " + root.taskInfo.rows.length : ""); color: root.secondary }
                Item { Layout.fillWidth: true }
                PC.Label { text: root.taskInfo.source === "DRM fdinfo" ? "Linux GPU driver" : (root.taskInfo.source || "Waiting for snapshot"); color: root.secondary; font.pointSize: PlasmaCore.Theme.smallestFont.pointSize }
            }
            RowLayout {
                Layout.fillWidth: true
                PC.TextField {
                    Layout.fillWidth: true
                    text: root.searchText
                    placeholderText: "Filter by process name or PID"
                    Accessible.name: "Filter GPU processes"
                    onTextEdited: root.searchText = text
                }
                PC.ToolButton { icon.name: "edit-clear"; enabled: root.searchText.length > 0; Accessible.name: "Clear process filter"; onClicked: root.searchText = "" }
                PC.ComboBox {
                    Layout.preferredWidth: units.gridUnit * 9
                    model: ["Memory usage", "GPU usage", "Process name"]
                    currentIndex: root.sortMode
                    Accessible.name: "Sort GPU processes"
                    onActivated: root.sortMode = index
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: units.smallSpacing * 2
                Layout.rightMargin: units.smallSpacing * 2
                PC.Label { text: "Process / PID"; color: root.secondary; Layout.fillWidth: true }
                PC.Label { text: "Type"; color: root.secondary; Layout.preferredWidth: units.gridUnit * 5.5 }
                PC.Label { text: "GPU memory"; color: root.secondary; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: units.gridUnit * 6 }
                PC.Label { text: "GPU %"; color: root.secondary; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: units.gridUnit * 4 }
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.rgba(PlasmaCore.Theme.textColor.r, PlasmaCore.Theme.textColor.g, PlasmaCore.Theme.textColor.b, 0.16) }
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: units.gridUnit * 7
                ListView {
                    id: taskList
                    anchors.fill: parent
                    clip: true
                    model: root.visibleTasks
                    spacing: 1
                    boundsBehavior: Flickable.StopAtBounds
                    QQC.ScrollBar.vertical: PC.ScrollBar {}
                    delegate: PC.ItemDelegate {
                        id: taskRow
                        width: taskList.width
                        height: units.gridUnit * 2.7
                        highlighted: root.selectedPID === String(modelData.pid)
                        opacity: root.healthy ? 1 : 0.55
                        Accessible.name: modelData.name + ", PID " + modelData.pid + ", memory " + root.processMemory(modelData.memoryBytes) + ", GPU " + root.processUsage(modelData.gpuUsage)
                        onClicked: root.selectedPID = root.selectedPID === String(modelData.pid) ? "" : String(modelData.pid)
                        QQC.ToolTip.visible: hovered
                        QQC.ToolTip.text: modelData.memoryKind + " · " + root.taskInfo.usageLabel + (modelData.note ? "\n" + modelData.note : "") + (modelData.sharedWith.length ? "\nShared with PID " + modelData.sharedWith.join(", ") : "")
                        contentItem: RowLayout {
                            spacing: units.smallSpacing
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 0
                                PC.Label { text: modelData.name; textFormat: Text.PlainText; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                                PC.Label { text: "PID " + modelData.pid + (modelData.sharedWith.length ? " · shared client" : ""); color: root.secondary; font.pointSize: PlasmaCore.Theme.smallestFont.pointSize }
                            }
                            PC.Label { text: modelData.kind; elide: Text.ElideRight; color: root.secondary; Layout.preferredWidth: units.gridUnit * 5.5 }
                            PC.Label { text: root.processMemory(modelData.memoryBytes); horizontalAlignment: Text.AlignRight; Layout.preferredWidth: units.gridUnit * 6 }
                            PC.Label { text: root.processUsage(modelData.gpuUsage); horizontalAlignment: Text.AlignRight; Layout.preferredWidth: units.gridUnit * 4; color: modelData.gpuUsage === null ? root.secondary : PlasmaCore.Theme.textColor }
                        }
                    }
                }
                ColumnLayout {
                    anchors.centerIn: parent
                    width: parent.width * 0.85
                    visible: root.visibleTasks.length === 0
                    spacing: units.smallSpacing
                    PC.Label { text: root.emptyTasks(); font.bold: true; Layout.alignment: Qt.AlignHCenter }
                    PC.Label {
                        text: root.searchText.length ? "Try a different process name or PID." : root.taskInfo.status === "loading" ? "The driver is collecting a fresh snapshot." : root.taskInfo.status === "unavailable" ? "Your driver or permissions may not expose process statistics." : root.taskInfo.source === "DRM fdinfo" ? "Your driver or permissions may hide processes or client statistics." : "A process can hold GPU memory without actively using the GPU."
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        color: root.secondary
                        Layout.fillWidth: true
                    }
                }
            }
            PC.Label {
                Layout.fillWidth: true
                visible: root.selectedPID.length > 0
                wrapMode: Text.WordWrap
                text: {
                    var row = root.taskInfo.rows.filter(function(p) { return String(p.pid) === root.selectedPID })[0]
                    return row ? row.name + " · " + row.memoryKind + (row.note ? "\n" + row.note : "") : "Process exited or is no longer visible."
                }
                color: root.secondary
                textFormat: Text.PlainText
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.rgba(PlasmaCore.Theme.textColor.r, PlasmaCore.Theme.textColor.g, PlasmaCore.Theme.textColor.b, 0.16) }
            PC.Label {
                Layout.fillWidth: true
                text: !root.healthy ? root.problem + " · showing the last task snapshot" : root.taskInfo.note
                wrapMode: Text.WordWrap
                color: root.secondary
                font.pointSize: PlasmaCore.Theme.smallestFont.pointSize
            }
            PC.Label {
                Layout.fillWidth: true
                text: "GPU %: " + root.taskInfo.usageLabel + ". — means unavailable, not idle."
                color: root.secondary
                font.pointSize: PlasmaCore.Theme.smallestFont.pointSize
            }
        }
    }
    Connections {
        target: plasmoid
        function onExpandedChanged() {
            if (plasmoid.expanded) root.requestSample()
            else { root.taskCache = ({}); root.tasksPaused = false; root.selectedPID = "" }
        }
    }

    PlasmaCore.DataSource {
        id: process
        engine: "executable"
        connectedSources: []
        onNewData: {
            disconnectSource(sourceName)
            root.sampling = false
            try {
                var sample = JSON.parse(data.stdout)
                if (sample.ok) {
                    root.cards = sample.cards
                    if (!root.selectedGPU && root.cards.length) root.selectedGPU = root.cards[0].id
                    if (sample.processDetails && !root.tasksPaused && root.wantsProcesses) {
                        var next = {}
                        root.cards.forEach(function(c) { if (c.processInfo) next[c.id] = c.processInfo })
                        root.taskCache = next
                    }
                    root.unavailableDevices = (sample.devices || []).filter(function(d) { return d.status !== "available" })
                    root.problem = sample.message || "No readable GPU sensors"
                    root.healthy = true
                    root.lastUpdate = Date.now()
                    if (root.wantsProcesses && !root.tasksPaused && !sample.processDetails) Qt.callLater(root.requestSample)
                }
                else { root.healthy = false; root.problem = sample.error }
            } catch (e) { root.healthy = false; root.problem = "GPU sensors unavailable" }
        }
    }
    Timer {
        interval: 3000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            if (root.lastUpdate && Date.now() - root.lastUpdate > 15000) { root.healthy = false; root.problem = "GPU readings are stale" }
            root.requestSample()
        }
    }
}
