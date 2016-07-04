# -*- coding: utf-8 -*-

##################################################################################################

import os

import xbmcgui
import xbmcaddon

##################################################################################################

addon = xbmcaddon.Addon('plugin.video.emby')

ACTION_BACK = 92
SIGN_IN = 200
REMIND_LATER = 201


class LoginConnect(xbmcgui.WindowXMLDialog):


    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def __add_editcontrol(self, x, y, height, width, password=0):
        
        media = os.path.join(addon.getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlEdit(0,0,0,0,
                            label="User",
                            font="font10",
                            textColor="ff464646",
                            focusTexture=os.path.join(media, "button-focus.png"),
                            noFocusTexture=os.path.join(media, "button-focus.png"),
                            isPassword=password)

        control.setPosition(x,y)
        control.setHeight(height)
        control.setWidth(width)

        self.addControl(control)
        return control

    def onInit(self):
        
        self.user_field = self.__add_editcontrol(685,385,40,500)
        self.setFocus(self.user_field)
        self.password_field = self.__add_editcontrol(685,470,40,500, password=1)
        self.signin_button = self.getControl(SIGN_IN)
        self.remind_button = self.getControl(REMIND_LATER)

        self.user_field.controlUp(self.remind_button)
        self.user_field.controlDown(self.password_field)
        self.password_field.controlUp(self.user_field)
        self.password_field.controlDown(self.signin_button)
        self.signin_button.controlUp(self.password_field)
        self.remind_button.controlDown(self.user_field)

    def onClick(self, control):

        if control == SIGN_IN:
            # Sign in to emby connect
            self.user = self.user_field.getText()
            __password = self.password_field.getText()

            ### REVIEW ONCE CONNECT MODULE IS MADE
            self.close()

        elif control == REMIND_LATER:
            # Remind me later
            self.close()

    def onAction(self, action):

        if action == ACTION_BACK:
            self.close()