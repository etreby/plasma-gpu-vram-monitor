import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.components 3.0 as PC
import org.kde.plasma.plasmoid 2.0

Item {
    id: root
    property var cards: []
    property bool healthy: false
    property string problem: "Loading GPU sensors…"
    property double lastUpdate: 0
    readonly property string command: "python3 " + shellQuote(decodeURIComponent(Qt.resolvedUrl("../scripts/gpu-panel-data.py").toString().replace(/^file:\/\//, "")))
    function shellQuote(value) { return "'" + value.replace(/'/g, "'\\''") + "'" }
    function temp(v) { return v === null || v === undefined ? "—" : Math.round(v) + "°" }
    function percent(v) { return v === null || v === undefined ? "—" : Math.round(v) + "%" }
    function memory(c) { return c.used === null || !c.total ? "—" : (c.used/1024).toFixed(1) + " / " + Math.round(c.total/1024) + " GiB" }
    function heat(v) { return v >= 95 ? PlasmaCore.Theme.negativeTextColor : v >= 80 ? PlasmaCore.Theme.neutralTextColor : PlasmaCore.Theme.textColor }
    function details() {
        if (!healthy) return problem
        return cards.map(function(c) { return c.name + "\nCore: " + temp(c.core) + "C · Hotspot: " + temp(c.junction) + "C · VRAM: " + temp(c.vram) + "C\nGPU load: " + percent(c.load) + " · Memory activity: " + percent(c.memoryLoad) + "\nVRAM used: " + memory(c) }).join("\n\n") + "\n\nUpdates every 3 seconds. Temperatures: core / VRAM."
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
        Layout.minimumWidth: units.gridUnit * Math.max(1, root.cards.length) * 14
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
                model: root.cards
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
            PC.Label { visible: root.cards.length === 0; text: root.problem; elide: Text.ElideRight; Layout.fillWidth: true; color: root.secondary }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: { compact.forceActiveFocus(); plasmoid.expanded = !plasmoid.expanded }
        }
    }
    Plasmoid.fullRepresentation: ColumnLayout {
        Layout.minimumWidth: units.gridUnit * 23
        Layout.preferredWidth: units.gridUnit * 23
        Layout.minimumHeight: implicitHeight
        spacing: units.largeSpacing
        PC.Label {
            text: "GPU & VRAM Monitor"
            font.bold: true
            font.pointSize: PlasmaCore.Theme.defaultFont.pointSize * 1.2
            Layout.topMargin: units.largeSpacing
            Layout.leftMargin: units.largeSpacing
        }
        Repeater {
            model: root.cards
            delegate: ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: units.largeSpacing
                Layout.rightMargin: units.largeSpacing
                spacing: units.smallSpacing
                PC.Label { text: modelData.name; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                RowLayout {
                    Layout.fillWidth: true
                    PC.Label { text: "Core  " + (root.healthy ? root.temp(modelData.core) : "—"); color: root.heat(modelData.core) }
                    Item { Layout.fillWidth: true }
                    PC.Label { text: "Hotspot  " + (root.healthy ? root.temp(modelData.junction) : "—"); color: root.heat(modelData.junction) }
                    Item { Layout.fillWidth: true }
                    PC.Label { text: "VRAM  " + (root.healthy ? root.temp(modelData.vram) : "—"); color: root.heat(modelData.vram) }
                }
                PC.ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: root.healthy ? root.ratio(modelData) : 0; Accessible.name: "VRAM allocation" }
                RowLayout {
                    Layout.fillWidth: true
                    PC.Label { text: root.healthy ? root.memory(modelData) + " VRAM" : "Readings unavailable"; color: root.secondary }
                    Item { Layout.fillWidth: true }
                    PC.Label { text: "GPU " + (root.healthy ? root.percent(modelData.load) : "—"); color: root.secondary }
                }
                PC.Label { text: "Memory activity  " + (root.healthy ? root.percent(modelData.memoryLoad) : "—"); color: root.secondary; font.pointSize: PlasmaCore.Theme.smallestFont.pointSize }
            }
        }
        PC.Label {
            text: root.healthy ? "Live · refreshes every 3 seconds" : root.problem
            color: root.healthy ? root.secondary : PlasmaCore.Theme.neutralTextColor
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.leftMargin: units.largeSpacing
            Layout.rightMargin: units.largeSpacing
            Layout.bottomMargin: units.largeSpacing
        }
    }
    PlasmaCore.DataSource {
        id: process
        engine: "executable"
        connectedSources: []
        onNewData: {
            disconnectSource(sourceName)
            try {
                var sample = JSON.parse(data.stdout)
                if (sample.ok) { root.cards = sample.cards; root.healthy = true; root.lastUpdate = Date.now() }
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
            if (process.connectedSources.length === 0) process.connectSource(root.command)
        }
    }
}
